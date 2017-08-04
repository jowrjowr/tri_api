def permissions(alliance_id):
    import MySQLdb as mysql
    import common.database as _database
    import common.logger as _logger

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
        return False

    try:
        query = 'SELECT forum, jabber, teamspeak, status FROM Permissions WHERE allianceID=%s'
        perm_count = cursor.execute(query, (alliance_id,))
        row = cursor.fetchone()
    except Exception as errmsg:
        _logger.log('[' + __name__ + '] mysql error: ' + str(errmsg), _logger.LogLevel.ERROR)
        return False
    finally:
        cursor.close()
        sql_conn.close()

    permissions = dict()

    if perm_count == 0:
        _logger.log('[' + __name__ + '] permissions table for alliance {0} not found'.format(alliance_id),_logger.LogLevel.DEBUG)

        permissions['forum'] = False
        permissions['jabber'] = False
        permissions['teamspeak'] = False
        permissions['status'] = False
    else:
        _logger.log('[' + __name__ + '] permissions table for alliance {0} found'.format(alliance_id),_logger.LogLevel.DEBUG)
        forum, jabber, teamspeak, status = row

        permissions['forum'] = forum
        permissions['jabber'] = jabber
        permissions['teamspeak'] = teamspeak
        permissions['status'] = status

    return(permissions)

def usertest(charid):
    # determine user status with more detail than blue or not

    import json
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger
    import common.request_esi

    # determine the status of the user and how to proceed
    _logger.log('[' + __name__ + '] determining status of {0}'.format(charid),_logger.LogLevel.INFO)

    # username

    esi_url = 'characters/{}/?datasource=tranquility'.format(charid)

    code, result = common.request_esi.esi(__name__, esi_url, 'get')
    _logger.log('[' + __name__ + '] /characters output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        return False, 'error', None

    charname = result['name']

    # character affiliations
    # doing via requests directly so no caching the request

    request_url = 'characters/affiliation/?datasource=tranquility'
    data = '[{}]'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, method='post', data=data)

    if not code == 200:
        _logger.log('[' + __name__ + '] affiliations API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        return False, 'error', None

    corpid = result[0]['corporation_id']
    try:
        allianceid = result[0]['alliance_id']
    except Exception as error:
        # the only way this can happen is if the character does not have an alliance.
        # unlikely but worth catching for completeness' sake
        _logger.log('[' + __name__ + '] User does not have an alliance: {0})'.format(charid), _logger.LogLevel.DEBUG)
        allianceid = 0


    # validate that the person who wants services is, in fact, blue to us
    request_url = 'core/isblue?id={0}'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, 'get', base='triapi')

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /isblue API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        return False, 'error', None

    isblue = result['code']
    # see if the user is already in the database, one way or the other.

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(objectclass=pilot)(uid={0}))'.format(charid)
    attributes = ['authGroup', 'accountStatus', 'altOf' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return False, 'error', None

    if result == None:

        _logger.log('[' + __name__ + '] ldap entry for {0} not found'.format(charid),_logger.LogLevel.DEBUG)
        # since the user isn't in the database, we can determine how to proceed based on blue status only
        if isblue == 0:
            _logger.log('[' + __name__ + '] charid {0} ({1}) is not blue'.format(charid,charname),_logger.LogLevel.WARNING)
            return False, 'public', None
        elif isblue == 1:
            # the user is blue and is otherwise eligible for services.
            _logger.log('[' + __name__ + '] charid {0} ({1}) is blue'.format(charid,charname),_logger.LogLevel.DEBUG)
            return True, 'unregistered', None
        else:
            _logger.log('[' + __name__ + '] isblue api error on charid {0} ({1})'.format(charid,charname),_logger.LogLevel.ERROR)
            return False, 'error', None
    else:
        _logger.log('[' + __name__ + '] ldap entry for {0} found'.format(charid),_logger.LogLevel.DEBUG)
    
    # past here, the user is validated to be in our database to some degree
    
    # account status is one of three things: 
    # public, banned, blue

    (dn, info), = result.items()
    status = info['accountStatus']
    altof = info['altOf']

    if altof == None or altof == 'None':
        isalt = False
    else:
        isalt = True

    if status == 'banned':
        # user is banned. 
        _logger.log('[' + __name__ + '] user tested to "banned"',_logger.LogLevel.INFO)
        return False, 'banned', None
    elif status == 'blue':
        # the user is already in the system, but not banned
        _logger.log('[' + __name__ + '] user tested to "blue"',_logger.LogLevel.INFO)

        if isalt == True:
            # is an alt
            return True, 'isalt', altof
        else:
            # is not an alt
            return True, 'registered', None
    elif status == 'public':
        # former user. no status.
        _logger.log('[' + __name__ + '] user tested to "public"',_logger.LogLevel.INFO)
        return False, 'public', None
    else:
        # should never happen
        _logger.log('[' + __name__ + '] user tested to "wtf?"',_logger.LogLevel.INFO)
        return False, 'error', None
