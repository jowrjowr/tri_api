def audit_discord():

    import common.logger as _logger
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import common.request_esi
    import redis
    import MySQLdb as mysql
    import re
    from collections import defaultdict

    # audit discord users for overlap with hostile discords + other things of interest

    # setup redis
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except redis.exceptions.ConnectionRefusedError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except Exception as err:
        logger.error('[' + __name__ + '] Redis generic error: ' + str(err))

    # setup mysql

    try:
        sql_conn = mysql.connect(
            database='discord',
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST,
            charset='utf8mb4',
        )
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    cursor = sql_conn.cursor()

    # find discord users in ldap

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(discordAccessToken=*)'
    attrlist = ['uid', 'corporation', 'characterName', 'authGroup']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        _logger.log('[' + __name__ + '] ldap error: {0}'.format(result), _logger.LogLevel.ERROR)
        return

    # friendly discord id hardcodes

    f_discords = []

    f_discords.append(301016648339423232)   # avalanche
    f_discords.append(212890573156253696)   # wombo
    f_discords.append(275395882415816705)   # no mercy
    f_discords.append(233545865053077504)   # steel fury
    f_discords.append(322163331047882754)   # unofficial vg
    f_discords.append(283533833326821376)   # quam
    f_discords.append(269991543627055114)   # vg leadership
    f_discords.append(186667149060734976)   # nullify
    f_discords.append(110544661776453632)   # superflous wanderlust

    # neutral discord hardcode. only useful for helping find an identity

    n_discords = []

    n_discords.append(243235450972536833)   # z-s overview
    n_discords.append(202724765218242560)   # /r/eve discord
    n_discords.append(108746777263415296)   # spectre fleet
    n_discords.append(285281772810403840)   # kugu
    n_discords.append(163975909580341249)   # scc lounge
    n_discords.append(222565109627617280)   # NETC
    n_discords.append(259950272065830912)   # pubg squad
    n_discords.append(81384788765712384)    # discord api
    n_discords.append(332880147810353153)   # book club
    n_discords.append(216398568049737728)   # weebfleet
    n_discords.append(299888109003472896)   # csm12
    n_discords.append(229744043737874434)   # zulu
    n_discords.append(336324139809767425)   # cap escalation [albion]
    n_discords.append(174613404005302272)   # talking in stations
    n_discords.append(296890122824187904)   # wspace pub
    n_discords.append(213691723329699841)   # ISD RUS
    n_discords.append(327311033771360256)   # crossout

    # fetch all the various discord tables

    sql_conn.select_db('information_schema')
    query = 'SELECT TABLE_NAME FROM TABLES WHERE TABLE_SCHEMA=%s'

    try:
        cursor.execute(query, ('discord',))
        tables = cursor.fetchall()
    except Exception as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return

    discords = []

    regex = r'^users_(\S+)$'
    for table, in tables:
        match = re.match(regex, table)

        if match: discords.append(match.group(1))

    # fetch all the members out of mysql and build a dict to look at relationships with

    sql_conn.select_db('discord')

    all_member = defaultdict(list)
    all_discord = defaultdict(list)

    for server in discords:

        server = int(server)

        table = 'users_{}'.format(server)

        query = "SELECT member_id, username, discriminator, member_nick, top_role, server_permissions FROM {0}".format(table)
        try:
            cursor.execute(query)
            discord_users = cursor.fetchall()
        except Exception as e:
            print(e)
            continue

        all_discord[server] = dict()

        for member_id, username, discriminator, member_nick, top_role, permissions in discord_users:
            # all servers a given member is on

            all_member[member_id].append(server)

            # information on this particular member
            server_info = dict()
            server_info['username'] = username
            server_info['discriminator'] = discriminator
            server_info['member_nick'] = member_nick
            server_info['permissions'] = permissions
            server_info['top_role'] = top_role

            all_discord[server][member_id] = server_info


    # now construct a dict of every friendly user

    f_users = set()

    for server in all_discord:

        if server in f_discords:
            # all the members in this discord are friendly

            # grab each member id out of the id, info tuple
            for user in all_discord[server]:
                f_users.add(user)


    for f_user in list(f_users):
        # check each friendly user for a presence on other servers

        servers = set(all_member[f_user])
        hostile = servers - set(f_discords) - set(n_discords)

        if len(hostile) == 0: continue

        # this user is on multiple other - possibly hostile - discords
        # not all are hostile, some are neutral-ish.

        # build out useful information

        f_servers = []
        h_servers = []
        n_servers = []

        username = None

        for server in list( servers ):

            server_info = all_discord[server][f_user]

            # literally the same across every server anyway
            username = '{0}#{1}'.format(server_info['username'], server_info['discriminator'])
            member_nick = server_info['member_nick']
            permissions = server_info['permissions']
            top_role = server_info['top_role']

            # map each server id to a name

            try:
                server_name = r.get(server)
                server_name = server_name.decode('utf-8')
            except Exception as e:
                server_name = server

            # show the identity used


            server_name = '{0} || server nick: {1} || top role: {2}'.format(server_name, member_nick, top_role)

            # classify the membership

            if server in f_discords:
                f_servers.append(server_name)
            elif server in n_discords:
                n_servers.append(server_name)
            else:
                h_servers.append(server_name)

        print('matching member: {0}'.format(username))
        print('friendly discords: {0}'.format(f_servers))
        print('hostile discords: {0}'.format(h_servers))
        print('neutral discords: {0}'.format(n_servers))
        print('\n')

    return

    f_users = dict()

    for dn, info in result.items():

        # fetch discord user info
        charid = info['uid']
        request_url = 'users/@me'
        code, result = common.request_esi.esi(__name__, request_url, base='discord', charid=charid, version='v6')

        if not code == 200:
            _logger.log('[' + __name__ + '] discord /users/@me API error {0}: {1}'.format(code, result), _logger.LogLevel.ERROR)
            continue

        discord_userid = result['id']

        f_users[charid] = dict()
        f_users[charid]['servers'] = set()

        # fetch discord connections

        request_url = 'users/@me/guilds'
        code, result = common.request_esi.esi(__name__, request_url, base='discord', charid=charid, version='v6')

        if not code == 200:
            _logger.log('[' + __name__ + '] discord /users/@me/guilds API error {0}: {1}'.format(code, result), _logger.LogLevel.ERROR)
            continue
        for server in result:
            # build the list of server ids a user is on
            server_id = server['id']

            f_users[charid]['servers'].add(server_id)


    print(f_users)
