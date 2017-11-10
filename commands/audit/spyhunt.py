def audit_security(targets=None):

    import common.request_esi
    import common.logger as _logger
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    from common.test_tor import test_tor
    import math
    import MySQLdb as mysql
    import time
    from maxminddb import open_database
    from collections import defaultdict

    # keep the ldap account status entries in sync



    if not targets == None:
        _logger.log('[' + __name__ + '] auditing CORE security log for specified targets',_logger.LogLevel.INFO)
    else:
        _logger.log('[' + __name__ + '] auditing CORE security log',_logger.LogLevel.INFO)

    # connections

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
        cursor = sql_conn.cursor()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    # fetch the last week's security log stuff

    time_range = time.time() - 86400*14
    cursor = sql_conn.cursor()

    time_range=0
    query = 'SELECT charID, charName, date, IP, action FROM Security WHERE date > FROM_UNIXTIME(%s)'
    try:
        cursor.execute(query, (time_range,))
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return
    finally:
        cursor.close()
        sql_conn.close()

    # build a few dicts of data for various usage

    nested_dict = lambda: defaultdict(nested_dict)
    data = nested_dict()
    ts3_logins = defaultdict(list)
    jabber_logins = defaultdict(list)

    all_ips = set()

    for charid, charname, date, IP, action in rows:
        # a quick dict of ip to charid associations
        data['ip'][IP][charid] = date

        # a quick dict of actions that tie charid and ip to the action

        data['action'][action][charid] = IP

        all_ips.add(IP)
        # build lists of ips based on specific actions
        if action == 'ts3 login':
            ts3_logins[charid].append(IP)
        if action == 'jabber login':
            jabber_logins[charid].append(IP)

    # test for tor

    ips = set(data['action'][IP])
    for ip in list(ips):
        # test if the ip is used on tor

        hostip = '144.217.252.208'
        is_tor = test_tor(hostip, IP)
        if is_tor == True:
            _logger.log('[' + __name__ + '] tor exit node: {0}'.format(IP),_logger.LogLevel.WARNING)
        else:
            _logger.log('[' + __name__ + '] not a tor exit: {0}'.format(IP),_logger.LogLevel.DEBUG)

    # load geoip shit

    geo_asn = open_database('/opt/geoip/GeoLite2-ASN.mmdb')
    geo_city = open_database('/opt/geoip/GeoLite2-City.mmdb')
    geo_country = open_database('/opt/geoip/GeoLite2-Country.mmdb')

    # test for AWS/azure/etc ASes
    # 16509 : AWS,

    aws = [ 16509, 14618, ]
    digocean = [ 393406, 14061 ]
    azure = [ 8075 ]

    bad_asns = aws + azure + digocean

    warning_charids = dict()

    for ip in list(all_ips):
        try:
            asn_detail = geo_asn.get(ip)
        except Exception as e:
            continue

        if asn_detail == None: continue
        asn = asn_detail.get('autonomous_system_number')
        asn_owner = asn_detail.get('autonomous_system_organization')

        if asn in bad_asns:
            charids = list(data['ip'][ip])

            for charid in charids:
                if charid == None:
                    continue
                # make sure the charid has a dict
                try:
                    warning_charids[charid]
                except KeyError:
                    warning_charids[charid] = dict()
                # make sure the charid dict has useful arrays
                try:
                    warning_charids[charid]['ips']
                    warning_charids[charid]['asns']
                    warning_charids[charid]['asn_owners']
                except KeyError:
                    warning_charids[charid]['ips'] = []
                    warning_charids[charid]['asns'] = []
                    warning_charids[charid]['asn_owners'] = []

                warning_charids[charid]['ips'].append(ip)
                warning_charids[charid]['asn_owners'].append(asn_owner)
                warning_charids[charid]['asns'].append(asn)
                _logger.log('[' + __name__ + '] ip {0} in bad asn {1} ({2})'.format(ip, asn, asn_owner),_logger.LogLevel.WARNING)
                _logger.log('[' + __name__ + '] ip {0} used by charids: {1}'.format(ip, charids),_logger.LogLevel.WARNING)


    for charid in warning_charids:
        ips = set( warning_charids[charid]['ips'] )
        asns = set( warning_charids[charid]['asns'] )
        asn_owners = set( warning_charids[charid]['asn_owners'] )

        msg1 = 'charid {0}:'.format(charid)
        msg2 = '\t bad ips: {0}'.format(ips)
        msg3 = '\t bad asns: {0}'.format(asn_owners)

        print(msg1)
        print(msg2)
        print(msg3)

    return

    for charid in jabber_logins:

        jabber_ips = set(jabber_logins[charid])
        ts3_ips = set(ts3_logins[charid])

        if jabber_ips == ts3_ips:
            # making the assumption that any relay will be on
            # a different server than the ts3 clients
            continue

        if jabber_ips == set():
            # nothing to check
            continue

        # start seeing what goes where with geoip

        ts3_country = set()

        for ip in ts3_ips:
            match = geo_country.get(ip)
            country = match['country']['iso_code']
            print('reeee: {}'.format(country))
            ts3_country.add(country)

        # dedupe
        ts3_country = list(ts3_country)
        _logger.log('[' + __name__ + '] ts3 country for charid {0} : {1}'.format(charid, ts3_country),_logger.LogLevel.DEBUG)

#        print(set(ts3_country))
#            print(match)
#        print(jabber_ips)

#    print(data)
    return

    # fetch all non-banned LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(!(accountstatus=banned))(!(accountStatus=immortal)))'
    attributes = ['uid', 'characterName', 'accountStatus', 'authGroup', 'corporation', 'alliance' ]
    code, users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return
    else:
        result_count = len(users)

    _logger.log('[' + __name__ + '] total non-banned ldap users: {}'.format(result_count),_logger.LogLevel.DEBUG)

    # bulk affiliations fetch

    data = []
    chunksize = 750 # current ESI max is 1000 but we'll be safe
    for user in users.keys():
        try:
            charid = int( users[user]['uid'] )
            data.append(charid)
        except Exception as error:
            pass
    length = len(data)
    chunks = math.ceil(length / chunksize)
    for i in range(0, chunks):
        chunk = data[:chunksize]
        del data[:chunksize]
        _logger.log('[' + __name__ + '] passing {0} items to affiliations endpoint'.format(len(chunk)), _logger.LogLevel.INFO)
        request_url = 'characters/affiliation/?datasource=tranquility'
        chunk = json.dumps(chunk)
        code, result = common.request_esi.esi(__name__, request_url, method='post', data=chunk)
        for item in result:

            # locate the dn from the charid
            charid = item['character_id']
            for user in users.keys():
                try:
                    ldap_charid = int( users[user]['uid'] )
                except Exception as error:
                    ldap_charid = None

                if ldap_charid == charid:
                    #print('matched dn {0} to uid {1} ldap charid {2}'.format(user, charid, ldap_charid))
                    dn = user

            users[dn]['esi_corp'] = item['corporation_id']
            if 'alliance_id' in item.keys():
                users[dn]['esi_alliance'] = item['alliance_id']
            else:
                users[dn]['esi_alliance'] = None

    # groups that a non-blue user is allowed to have

    safegroups = set([ 'public', 'ban_pending' ])

    # loop through each user and determine the correct status

    for user in users.keys():
        dn = user

        if users[user]['uid'] == None:
            continue

        charid = int(users[user]['uid'])
        status = users[user]['accountStatus']
        charname = users[user]['characterName']
        groups = users[user]['authGroup']

        # bad data protection
        try:
            esi_allianceid = users[user]['esi_alliance']
        except:
            esi_allianceid = None
        try:
            ldap_allianceid = int(users[user]['alliance'])
        except:
            ldap_allianceid = None
        try:
            esi_corpid = users[user]['esi_corp']
        except:
            esi_corpid = None
        try:
            ldap_corpid = int(users[user]['corporation'])
        except:
            ldap_corpid = None
        # user's effective managable groups
        groups = list( set(groups) - safegroups )

        # tinker with ldap to account for reality

        if not esi_allianceid == ldap_allianceid:
            # update a changed alliance id
            _ldaphelpers.update_singlevalue(dn, 'alliance', str(esi_allianceid))
        if not esi_corpid == ldap_corpid:
            # update a changed corp id
            _ldaphelpers.update_singlevalue(dn, 'corporation', str(esi_corpid))

        if status == 'blue':
            # blue in ldap

            if not esi_allianceid in vanguard:
                # need to adjust to public
                _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'public')

            # give them the correct base authgroups

            if esi_allianceid == triumvirate and 'triumvirate' not in groups:
                # all tri get trimvirate
                _ldaphelpers.add_value(dn, 'authGroup', 'triumvirate')

            if 'vanguard' not in groups:
                # all blue get vanguard
                _ldaphelpers.add_value(dn, 'authGroup', 'vanguard')

        else:
            # not blue in ldap, obv
            if len(groups) > 0:
                # purge groups off someone who has more than they should
                # not a security issue per se, but keeps the management tools clean
                _ldaphelpers.purge_authgroups(dn, groups)
            if esi_allianceid in vanguard:
                # oops. time to fix you.
                _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'blue')

