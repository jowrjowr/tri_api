def teamspeak_groups(charid):

    # make sure the ts user has the correct groups

    import json
    import ldap
    import ldap.modlist
    import ts3
    import MySQLdb as mysql
    import common.request_esi
    import common.logger as _logger
    import common.credentials.ldap as _ldap
    import common.credentials.ts3 as _ts3
    import common.database as _database

    # initialize connections

    try:
        ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        msg = 'LDAP connection error: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return(False, msg)
    # what can this alliance in terms of services?

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
        cursor = sql_conn.cursor()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return(False)

    try:
        # Note, that the client will wait for the response and raise a
        # **TS3QueryError** if the error id of the response is not 0.
        ts3conn = ts3.query.TS3Connection(_ts3.TS_HOST)
        ts3conn.login(
            client_login_name=_ts3.TS_USER,
            client_login_password=_ts3.TS_PASSWORD
        )
    except ts3.query.TS3QueryError as err:
        msg = 'unable to connect to TS3: {0}'.format(err.resp.error["msg"])
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        return(False, msg)

    ts3conn.use(sid=_ts3.TS_SERVER_ID)

    # snag existing ts info. this will matter later.
    try:
        result = ldap_conn.search_s('ou=People,dc=triumvirate,dc=rocks',
            ldap.SCOPE_SUBTREE,
            filterstr='(uid={})'.format(charid),
            attrlist=['teamspeakdbid', 'characterName', 'authGroup', 'corporation', 'alliance' ]
        )
        result_count = result.__len__()
    except ldap.LDAPError as error:
        msg = 'unable to fetch ldap users: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return(False, msg)

    if result_count == 0:
        # this should NEVER happen
        msg = 'charid {0} not in ldap'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return(False, msg)

    dn, result = result[0]
    encodedgroups = result['authGroup']
    ldap_groups = []
    for group in encodedgroups:
        ldap_groups.append(group.decode('utf-8'))

    charname = result['characterName'][0].decode('utf-8')
    try:
        allianceid = int( result['alliance'][0].decode('utf-8') )
    except error as e:
        allianceid = 0
    try:
        corpid = int( result['corporation'][0].decode('utf-8') )
    except error as e:
        corpid = 0
    try:
        ts_dbid = result['teamspeakdbid'][0].decode('utf-8')
    except Exception as error:
        ts_dbid = None

    if ts_dbid == None:
        # we have a live account. nuke it and try again.
        msg = 'no existing teamspeak client for charid {0}'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        return(False, msg)

    # get character ts groups

    try:
        resp = ts3conn.servergroupsbyclientid(cldbid=ts_dbid)
        tsgroups = resp.parsed
    except ts3.query.TS3QueryError as err:
        msg = 'ts3 error: "{0}"'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return(False, msg)

    # the array of ts group ids the user has
    current_tsgroups = []
    for group in tsgroups:
        current_tsgroups.append( int(group['sgid']) )

    # snag mysql permissions info

    try:
        query = 'SELECT teamspeak FROM Permissions WHERE allianceID=%s '
        query += 'UNION SELECT teamspeak from BluePermissions WHERE allianceID=%s'
        perm_count = cursor.execute(query, (allianceid, allianceid))
        row = cursor.fetchone()
    except Exception as errmsg:
        _logger.log('[' + __name__ + '] mysql error: ' + str(errmsg), _logger.LogLevel.ERROR)
        return(False, errmsg)
    finally:
        cursor.close()
        sql_conn.close()

    if perm_count == 0:
        msg = 'no teamspeak available for charid {0}'.format(charid)
        return(False, msg)

    # start building out the array of groups this char should have

    correct_ts_groups = [ int(row[0]) ]

    # these TS groups are temporary/otherwise not subject to automated management. eg, logi tag.
    ignored_tsgroups = [ 8, 15, 16, 17, 18, 19, 20 ]

    # these LDAP groups are managed in different ways.
    ignored_ldapgroups = [ 'vanguard', 'vanguardBlue', 'public', 'triumvirate' ]

    # set difference to find the effective ts groups that we'll manage

    current_ts_groups = list ( set(current_tsgroups) - set(ignored_tsgroups) )
    ldap_groups = list( set(ldap_groups) - set(ignored_ldapgroups) )

    # ts server admin group 6

    # discover corp group

    if allianceid == 933731581:
        # only tri corps get corp server groups
        try:
            resp = ts3conn.servergrouplist()
            tsgroups = resp.parsed
        except ts3.query.TS3QueryError as err:
            msg = 'ts3 error: "{0}"'.format(err)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return(False, msg)

        # get the corp info

        request_url = 'corporations/{0}/'.format(corpid)
        code, result = common.request_esi.esi(__name__, request_url, 'get', version='v4')

        if code != 200:
            # something broke severely
            _logger.log('[' + __name__ + '] corporations API error {0}: {1}'.format(code, result['error']),
                        _logger.LogLevel.ERROR)
            error = result['error']
            result = {'code': code, 'error': error}
            return False, result

        corp_name = result['name']
        corp_ticker = result['ticker']

        # the group name is referred to by ticker

        corp_groupid = None

        for group in tsgroups:
            if group['name'] == corp_ticker:
                corp_groupid = int(group['sgid'])

        if corp_groupid:
            correct_ts_groups.append(corp_groupid)

    # groups for special authgroups

    for group in ldap_groups:
        try:
            result = ldap_conn.search_s('ou=Groups,dc=triumvirate,dc=rocks',
                ldap.SCOPE_SUBTREE,
                filterstr='(cn={})'.format(group),
                attrlist=[ 'teamspeak' ]
            )
            result_count = result.__len__()
        except ldap.LDAPError as error:
            msg = 'unable to fetch ldap group: {}'.format(error)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return(False, msg)

        if result_count == 0:
            # this should NEVER happen
            msg = 'group {0} not in ldap'.format(group)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return(False, msg)

        dn, result = result[0]

        try:
            teamspeak = result['teamspeak'][0].decode('utf-8')
            correct_ts_groups.append( int(teamspeak) )
        except Exception as error:
            # not everything has a ts group
            pass

    # now, we have the list of groups that the user is in, and the list of groups the user needs to be in

    # group addition
    groups_to_add = list( set(correct_ts_groups) - set(current_ts_groups) )
    msg = 'TS groups to add {0}'.format(groups_to_add)
    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)
    for group in groups_to_add:
        try:
            resp = ts3conn.servergroupaddclient(sgid=group, cldbid=ts_dbid)
        except ts3.query.TS3QueryError as err:
            msg = 'ts3 error: "{0}"'.format(err)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return(False, msg)
        msg = 'added TS group {0} to charid {1}'.format(group, charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)

    # group removal
    groups_to_remove = list( set(current_ts_groups) - set(correct_ts_groups) )
    msg = 'TS groups to remove {0}'.format(groups_to_remove)
    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)

    for group in groups_to_remove:

        try:
            resp = ts3conn.servergroupdelclient(sgid=group, cldbid=ts_dbid)
        except ts3.query.TS3QueryError as err:
            msg = 'ts3 error: "{0}"'.format(err)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return(False, msg)
        msg = 'added TS group {0} to charid {1}'.format(group, charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)

    return(True, 'blah')
