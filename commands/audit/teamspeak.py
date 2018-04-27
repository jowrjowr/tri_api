import asyncio

def audit_teamspeak():

    import common.credentials.ts3 as _ts3
    import common.logger as _logger

    import ts3

    # invididual tasks for teamspeak
    # http://py-ts3.readthedocs.io/en/latest/

    _logger.log('[' + __name__ + '] auditing teamspeak',_logger.LogLevel.INFO)

    # ts3 errorhandling is goofy.
    # if it can't find the user, it raises an error so we'll just assume failure means no user
    # and continue

    try:
        # Note, that the client will wait for the response and raise a
        # **TS3QueryError** if the error id of the response is not 0.
        ts3conn = ts3.query.TS3Connection(_ts3.TS_HOST)
        ts3conn.login(
            client_login_name=_ts3.TS_USER,
            client_login_password=_ts3.TS_PASSWORD
        )
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] unable to connect to TS3: {0}'.format(err.resp.error["msg"]),_logger.LogLevel.ERROR)
        return


    ts3conn.use(sid=_ts3.TS_SERVER_ID)

    ts3_logs(ts3conn)
    ts3_monitoring(ts3conn)
    ts3_validate_users(ts3conn)

def ts3_logs(ts3conn):

    import common.credentials.ts3 as _ts3
    import common.logger as _logger
    import redis
    import ts3
    import time
    import re

    # parse ts3 server logs and dump useful things into security log

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except redis.exceptions.ConnectionRefusedError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except Exception as err:
        logger.error('[' + __name__ + '] Redis generic error: ' + str(err))

    # is there another instance running?

    try:
        if r.get('ts_log_processing') is not None:
            msg = 'existing TS log processing running. skipping.'
            _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.WARNING)
            return
        else:
            r.set('ts_log_processing', 'yep')

    except Exception as err:
        _logger.log('[' + __name__ + '] Redis error: ' + str(err), _logger.LogLevel.ERROR)
        return

    # we start from a zero position and work our way back to a checkpoint in redis

    try:
        checkpoint = r.get('ts_log_checkpoint')
        checkpoint = float(checkpoint.decode('utf-8'))
    except Exception as err:
        _logger.log('[' + __name__ + '] Redis error: ' + str(err), _logger.LogLevel.ERROR)

    position = 1
    stop = False
    logcount = 0

    while position > 0 and stop == False:
        # a small position offset so i can start/stop cleanly
        if position == 1:
            position = 0

        try:
            resp = ts3conn.logview(lines=100, reverse=1, begin_pos=position)
        except ts3.query.TS3QueryError as err:
            _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.ERROR)
        for line in resp.parsed:
            if 'last_pos' in line.keys():
                file_size = line['file_size']
                last_pos = line['last_pos']
                position = int(last_pos)
                _logger.log('[' + __name__ + '] ts3 log size: {0}, last position: {1}'.format(file_size, last_pos),_logger.LogLevel.DEBUG)
            if 'l' in line.keys():
                logcount += 1
                entry = line['l']
                # parse the log

                try:
                    date, level, target, server, logline = entry.split('|', 4)
                except ValueError as err:
                    _logger.log('[' + __name__ + '] ts3 log line unparsable: {0}'.format(logline),_logger.LogLevel.ERROR)
                    continue
                # convert the date into epoch

                # example date: 2017-05-13 14:34:58.223587
                # or 0000002017-07-21 19:50:58.

                # why are you doing this shit, ts3?
                date = date.replace('000000', '')
                date = re.sub('\.$', '.000000', date) # make sure %f has something to use
                try:
                    date = time.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError as e:
                    _logger.log('[' + __name__ + '] ts3 log data pollution: {0}'.format(e),_logger.LogLevel.ERROR)
                    continue

                date = time.mktime(date)

                # stop processing logs as this is where we last were
                if date <= checkpoint:
                    stop = True
                    position = 0
                    break

                # regex out login events

                # example line:
                # client connected 'Sightless 1'(id:1615) from 135.23.200.132:50743

                loginmatch = re.match( r"^client connected \'(.*)\'\(id:(.*)\) from (.*):(.*)$", logline, re.M)
                if loginmatch:
                    charname = loginmatch.group(1)
                    clientid = loginmatch.group(2)
                    ip = loginmatch.group(3)

                    # dump the result into the security log
                    _logger.securitylog(__name__, 'ts3 login', charname=charname, ipaddress=ip, date=date)


    _logger.log('[' + __name__ + '] new ts3 log entries: {0}'.format(logcount),_logger.LogLevel.INFO)

    # set the redis checkpoint time for the next run

    checkpoint = time.time()
    try:
        r.set('ts_log_checkpoint', checkpoint)
        r.delete('ts_log_processing')
    except Exception as err:
        _logger.log('[' + __name__ + '] Redis error: ' + str(err), _logger.LogLevel.ERROR)


def ts3_monitoring(ts3conn):

    from common.graphite import sendmetric
    import common.credentials.ts3 as _ts3
    import common.logger as _logger

    import ts3

    # server statistics/information
    # might as well log some useful shit

    try:
        resp = ts3conn.serverrequestconnectioninfo()
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.ERROR)
        return

    for stat in resp.parsed[0]:
        sendmetric(__name__, 'ts3', 'server_stats', stat, resp.parsed[0][stat])

    try:
        resp = ts3conn.serverinfo()
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.ERROR)
        return

    # useful metrics as per the ts3 server query guide

    metrics = [ 'connection_bandwidth_sent_last_minute_total', 'connection_bandwidth_received_last_minute_total', ]

    for metric in metrics:
        sendmetric(__name__, 'ts3', 'vserver_{}'.format(_ts3.TS_SERVER_ID), metric, resp.parsed[0][metric])

    # log settings

    # need to ensure that the TS3 server has the logging settings desired, since there's
    # nothing in the ini that lets you set this information

    # this can be pivoted to managing settings as well

    # they come out as str() rather than int()
    logsettings = dict()
    logsettings['virtualserver_log_channel'] = int(resp.parsed[0]['virtualserver_log_channel'])
    logsettings['virtualserver_log_permissions'] = int(resp.parsed[0]['virtualserver_log_permissions'])
    logsettings['virtualserver_log_filetransfer'] = int(resp.parsed[0]['virtualserver_log_filetransfer'])
    logsettings['virtualserver_log_query'] = int(resp.parsed[0]['virtualserver_log_query'])
    logsettings['virtualserver_log_client'] = int(resp.parsed[0]['virtualserver_log_client'])
    logsettings['virtualserver_log_server'] = int(resp.parsed[0]['virtualserver_log_server'])

    for setting in logsettings:
        if logsettings[setting] == 0:
            _logger.log('[' + __name__ + '] ts3 log option {0} disabled'.format(setting),_logger.LogLevel.WARNING)

def ts3_validate_users(ts3conn):

    import ldap
    import common.ldaphelpers as _ldaphelpers
    import common.credentials.ldap as _ldap
    import common.credentials.ts3 as _ts3
    import common.logger as _logger
    import time
    import ts3

    from tri_core.common.tsgroups import teamspeak_groups


    try:
        ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        msg = 'LDAP connection error: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)


    # generic purge of TS from non-blue ldap users
    # only matches people who should not have a TS identity

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(!(accountStatus=blue))(teamspeakuid=*))'
    attributes = ['characterName', 'uid', 'esiAccessToken' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return

    if result == None:
        # nobody. no problem.
        pass
    else:
        result_count = len(result)
        # some ppl are banned/whatever and have a TS identity!
        msg = '{0} unauthorized users with a TS identity'.format(result_count)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)

        for user in result.keys():

            charid = int( result[user]['uid'] )

            # decouple their TS identities from their LDAP entry

            mod_attrs = []
            mod_attrs.append((ldap.MOD_DELETE, 'teamspeakdbid', None ))
            mod_attrs.append((ldap.MOD_DELETE, 'teamspeakuid', None ))
            try:
                ldap_conn.modify_s(user, mod_attrs)
                msg = 'purged TS identity from unauthorized user: {}'.format(user)
                _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)
            except ldap.LDAPError as error:
                _logger.log('[' + __name__ + '] unable to purge TS entries for {0}: {1}'.format(dn, error),_logger.LogLevel.ERROR)

    # validate ts3 online users

    # skip these users
    skip = [ 'ServerQuery Guest', 'sovereign' ]

    # it turns out clientdblist() are just users who are online, rather than ALL users or something
    # this does not audit users-within-groups apparently
    try:
        resp = ts3conn.clientdblist()
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.ERROR)
        return

    clients = []

    for user in resp.parsed:
        serviceuser = user['client_nickname']
        if serviceuser in skip:
            # we don't want to waste time on internal users
            continue
        clients.append(int(user['cldbid']))

    # get the rest of the clients out of the various groups, then de-dupe

    try:
        resp = ts3conn.servergrouplist()
        groups = resp.parsed
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.ERROR)
        return

    for group in groups:
        # dig out all the users in each group
        groupid = int(group['sgid'])

        skip = [ 8 ]

        if groupid in skip:
            # TS does NOT like looking into default groups (?)
            continue
        try:
            resp = ts3conn.servergroupclientlist(sgid=group['sgid'])
            result = resp.parsed
        except ts3.query.TS3QueryError as err:
            _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.ERROR)
            return
        for client in result:
            clients.append(int(client['cldbid']))

    # deduplicate using set and filter out dbids that have to be skipped
    # server query only, basically

    skip = [ 1 ]

    clients = set(clients) - set(skip)
    clients = list(clients)

    clientcount = len(clients)
    _logger.log('[' + __name__ + '] distinct ts3 client identities: {0}'.format(clientcount),_logger.LogLevel.DEBUG)

    # get the current TS3 client list
    try:
        resp = ts3conn.clientlist()
        live_clients = resp.parsed
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] unable to fetch TS client list: {0}'.format(err),_logger.LogLevel.WARNING)


    # start validating clients, online or otherwise
    for ts_dbid in clients:

        # this should never fail since the dbid we have is fed from the ts3 client list upstream

        try:
            resp = ts3conn.clientdbinfo(cldbid=ts_dbid)
            user = resp.parsed
        except ts3.query.TS3QueryError as err:
            _logger.log('[' + __name__ + '] ts3 (uid: {0}) error: "{1}"'.format(ts_dbid, err),_logger.LogLevel.WARNING)
            return

        user_nick = user[0]['client_nickname']
        _logger.log('[' + __name__ + '] Validating ts3 user "{0}"'.format(user_nick),_logger.LogLevel.DEBUG)

        user_lastip = user[0]['client_lastip']
        user_lastconn = int(user[0]['client_lastconnected'])
        user_conns = int(user[0]['client_totalconnections'])
        user_created = int(user[0]['client_created'])

        token = None # for token checks later
        orphan = False # for detached TS registrations
        kicked = False # users can be kicked in a few spots prior to final purge spot

        # we explicitly check only for blue users that have this dbid.
        # this means people with non-blue status (public, banned) lose their TS

        dn = 'ou=People,dc=triumvirate,dc=rocks'
        filterstr='(&(accountStatus=blue)(teamspeakdbid={}))'.format(ts_dbid)
        attrlist=['characterName', 'uid', 'esiAccessToken' ]

        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

        if code == False:
            return

        if result == None:
            # this can happen if the TS user has an entry in the TS db but nothing in ldap
            # this user will be dealt with downstream
            _logger.log('[' + __name__ + '] ts3 orphan dbid: {0}'.format(ts_dbid),_logger.LogLevel.INFO)
            registered_username = None
            orphan = True


        elif len(result) == 1:
            # the dbid is matched to an single ldap user
            (dn, info), = result.items()
            charname = info['characterName']
            charid = int( info['uid'] )
            registered_username = charname

            try:
                token = info['esiAccessToken']
            except Exception as e:
                token = None

            _logger.log('[' + __name__ + '] charid {0} validated non-orphan'.format(charid),_logger.LogLevel.DEBUG)

            # do a TS group validate

            code, result = teamspeak_groups(charid)

            if code == False:
                msg = 'unable to setup teamspeak groups for {0}: {1}'.format(charname, result)
                _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
                return

        elif len(result) > 1:
            # multiple TS registrations. naughty.

            _logger.log('[' + __name__ + '] multiple unique TS identities attached to accounts: {0}'.format(result),_logger.LogLevel.WARNING)

            orphan = True
            # boot from TS...
            reason = 'Please re-register your TS on CORE. On only one character.'
            try:
                resp = ts3conn.clientkick(reasonid=5, reasonmsg=reason, clid=clid)
                _logger.log('[' + __name__ + '] ts3 user {0} kicked from server: active orphan'.format(user_nick),_logger.LogLevel.WARNING)
                _logger.log('[' + __name__ + '] TS db: "{0}", client: "{1}"'.format(registered_username,client_username),_logger.LogLevel.DEBUG)
                kicked = True
                _logger.securitylog(__name__, 'ts3 duplicate character', charname=registered_username, date=user_lastconn, ipaddress=user_lastip)
            except ts3.query.TS3QueryError as err:
                _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.ERROR)

            # ...break the ldap <--> TS link on each character
            for user in result.keys():

                charid = int( result[user]['uid'] )

                mod_attrs = []
                mod_attrs.append((ldap.MOD_DELETE, 'teamspeakdbid', None ))
                mod_attrs.append((ldap.MOD_DELETE, 'teamspeakuid', None ))
                try:
                    ldap_conn.modify_s(user, mod_attrs)
                    msg = 'purged TS identity from duplicate user: {}'.format(user)
                    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)
                except ldap.LDAPError as error:
                    _logger.log('[' + __name__ + '] unable to purge TS entries for {0}: {1}'.format(dn, error),_logger.LogLevel.ERROR)


        # if the user is online, we want to make sure that the username matches
        # what is in the teamspeak table

        for client in live_clients:
            clid = client['clid']
            cldbid = int(client['client_database_id'])
            client_username = client['client_nickname']


            if orphan is True and cldbid == ts_dbid:
                # a registered TS user needs to have an ESI token on their LDAP
                reason = 'You are no longer registered on CORE'

                try:
                    resp = ts3conn.clientkick(reasonid=5, reasonmsg=reason, clid=clid)
                    _logger.log('[' + __name__ + '] ts3 user {0} kicked from server: no active registration'.format(user_nick),_logger.LogLevel.WARNING)
                    _logger.log('[' + __name__ + '] TS db: "{0}", client: "{1}"'.format(registered_username,client_username),_logger.LogLevel.DEBUG)
                    kicked = True
                    _logger.securitylog(__name__, 'ts3 without ESI', charname=registered_username, date=user_lastconn, ipaddress=user_lastip)
                except ts3.query.TS3QueryError as err:
                    _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.ERROR)

            if not client_username or not registered_username:
                continue

            if client_username.lower() == registered_username.lower() and token == None and kicked == False:
                # a registered TS user needs to have an ESI token on their LDAP
                reason = 'Please login to CORE. Your token has become invalid.'
                try:
                    resp = ts3conn.clientkick(reasonid=5, reasonmsg=reason, clid=clid)
                    _logger.log('[' + __name__ + '] ts3 user {0} kicked from server: no esi token'.format(user_nick),_logger.LogLevel.WARNING)
                    _logger.log('[' + __name__ + '] TS db: "{0}", client: "{1}"'.format(registered_username,client_username),_logger.LogLevel.DEBUG)
                    kicked = True
                    _logger.securitylog(__name__, 'ts3 without ESI', charname=registered_username, date=user_lastconn, ipaddress=user_lastip)
                except ts3.query.TS3QueryError as err:
                    _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.ERROR)

            if cldbid == ts_dbid and client_username != registered_username and kicked == False:
                # online user has a username that does not match records.
                # "encourage" fixing this.
                reason = 'Please use your main character name as your teamspeak nickname, without any tags'
                try:
                    resp = ts3conn.clientkick(reasonid=5, reasonmsg=reason, clid=clid)
                    _logger.log('[' + __name__ + '] ts3 user {0} kicked from server: mismatch'.format(user_nick),_logger.LogLevel.WARNING)
                    _logger.log('[' + __name__ + '] TS db: "{0}", client: "{1}"'.format(registered_username,client_username),_logger.LogLevel.DEBUG)
                    _logger.securitylog(__name__, 'ts3 name mismatch', charname=registered_username, date=user_lastconn, ipaddress=user_lastip, detail='wrong name: {0}'.format(client_username))
                    kicked = True
                except ts3.query.TS3QueryError as err:
                    _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.ERROR)

        # handle orphan TS users

        if orphan == True:
            # log the shit out of the orphan user

            lastconnected = time.gmtime(user_lastconn)
            lastconnected_iso = time.strftime("%Y-%m-%dT%H:%M:%S", lastconnected)
            created = time.gmtime(user_created)
            created_iso = time.strftime("%Y-%m-%dT%H:%M:%S", created)
            _logger.log('[' + __name__ + '] Orphan ts3 user: {0}'.format(user_nick), _logger.LogLevel.WARNING)
            _logger.log('[' + __name__ + '] User {0} created: {1}, last login: {2}, last ip: {3}, total connections: {4}'.format(
                user_nick,created_iso,lastconnected_iso,user_lastip,user_conns),
                _logger.LogLevel.WARNING
            )


            # first kick from the server if they are on, asking them to re-register
            # to do that i need the client id, which is not the client db id, because
            # of fucking course it isn't

            for client in live_clients:
                clid = client['clid']
                cldbid = client['client_database_id']
                if cldbid == ts_dbid and kicked == False:
                    try:
                        reason = 'You are detached from CORE. Please configure services.'
                        resp = ts3conn.clientkick(reasonid=5, reasonmsg=reason, clid=clid)
                        _logger.log('[' + __name__ + '] ts3 user {0} kicked from server (orphan user)'.format(user_nick),_logger.LogLevel.WARNING)
                        _logger.securitylog(__name__, 'orphan ts3 user', charname=user_nick, date=user_lastconn, ipaddress=user_lastip)
                    except ts3.query.TS3QueryError as err:
                        _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.WARNING)

            # now remove the client from the ts3 database

            try:
                resp = ts3conn.clientdbdelete(cldbid=ts_dbid)
                _logger.log('[' + __name__ + '] ts3 user {0} removed'.format(user_nick),_logger.LogLevel.WARNING)
            except ts3.query.TS3QueryError as err:
                _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.WARNING)

            # client removed. gg.
        else:
            # nothing to do. yer good.
            pass
