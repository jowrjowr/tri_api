import asyncio

def audit_teamspeak():

    import common.database as _database
    import common.jabber as _jabber
    import common.ts3 as _ts3
    import common.logger as _logger

    import logging
    import requests
    import json
    import ts3

    import common.request_esi

    _logger.log('[' + __name__ + '] auditing teamspeak',_logger.LogLevel.DEBUG)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # http://py-ts3.readthedocs.io/en/latest/

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

    # ts3 errorhandling is goofy.
    # if it can't find the user, it raises an error so we'll just assume failure means no user
    # and continue


    # it turns out clientdblist() are just users who are online or something.
    # this does not audit users-within-groups apparently

    try:
        resp = ts3conn.clientdblist()
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.WARNING)

    loop = asyncio.new_event_loop()

    for user in resp.parsed:
        serviceuser = user['client_nickname']
        _logger.log('[' + __name__ + '] Validating ts3 user {0}'.format(serviceuser),_logger.LogLevel.DEBUG)

        # not really proper clients, so don't do anything

        if serviceuser == 'ServerQuery Guest':
            pass
        elif serviceuser == 'sovereign':
            pass
        else:
            # otherwise:

            ts3_userid = user['cldbid']
            loop.run_until_complete(user_validate(ts3_userid))


    # iterate through ts3 groups and validate assigned users

    try:
        resp = ts3conn.servergrouplist()
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.WARNING)

    for group in resp.parsed:
        groupname = group['name']
        groupid = group['sgid']
        _logger.log('[' + __name__ + '] Validating ts3 group ({0}) {1}'.format(groupid, groupname),_logger.LogLevel.DEBUG)
        loop.run_until_complete(group_validate(groupid))

    loop.close()
    return ''


async def group_validate(ts3_groupid):

    # iterate through a given ts3 group and validate each individual userid
    import common.ts3 as _ts3
    import common.logger as _logger

    import logging
    import requests
    import json
    import time
    import ts3
    import asyncio

    # do not validate certain group ids
    # gid 8: guest

    skip = [ '8' ]

    for skip_id in skip:
        if skip_id == ts3_groupid:
            return

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

    try:
        resp = ts3conn.servergroupclientlist(sgid=ts3_groupid)
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: {0}'.format(err),_logger.LogLevel.WARNING)

    loop = asyncio.get_event_loop()

    for user in resp.parsed:
        user_id = user['cldbid']
        loop.run_until_complete(user_validate(user_id))

async def user_validate(ts3_userid):

    # validate a given user against the core database
    import MySQLdb as mysql
    import common.database as _database
    import common.ts3 as _ts3
    import common.logger as _logger

    import logging
    import requests
    import json
    import time
    import ts3

    # do not validate certain user ids
    # uid 1: admin
    skip = [ '1' ]

    for skip_id in skip:
        if skip_id == ts3_userid:
            return
    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return

    cursor = sql_conn.cursor()
    query = 'SELECT ClientDBID FROM Teamspeak WHERE ClientDBID = %s'

    try:
        row = cursor.execute(query, (ts3_userid,))
    except Exception as errmsg:
        _logger.log('[' + __name__ + '] mysql error: ' + str(errmsg), _logger.LogLevel.ERROR)
        js = json.dumps({ 'code': -1, 'error': 'mysql broke: ' + str(errmsg)})
        resp = Response(js, status=401, mimetype='application/json')
        return resp
    finally:
        cursor.close()
        sql_conn.commit()
        sql_conn.close()

    # a nonzero return means the ts3 user is linked to an active core user

    if row == 1:
        # we're done.
        #_logger.log('[' + __name__ + '] ...user {0} valid'.format(serviceuser),_logger.LogLevel.DEBUG)
        return

    # oops orphan. we hate orphans.
    # log the everloving shit out of this

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

    try:
        resp = ts3conn.clientdbinfo(cldbid=ts3_userid)
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 (uid: {0}) error: "{1}"'.format(ts3_userid, err),_logger.LogLevel.WARNING)

    user = resp.parsed
    user_nick = user[0]['client_nickname']
    user_lastip = user[0]['client_lastip']
    user_lastconn = int(user[0]['client_lastconnected'])
    user_conns = int(user[0]['client_totalconnections'])
    user_created = int(user[0]['client_totalconnections'])

    # log the shit out of the orphan user

    lastconnected = time.gmtime(user_lastconn)
    lastconnected_iso = time.strftime("%Y-%m-%dT%H:%M:%S", lastconnected)
    created = time.gmtime(user_created)
    created_iso = time.strftime("%Y-%m-%dT%H:%M:%S", created)
    _logger.log('[' + __name__ + '] Orphan ts3 user: {0}'.format(user_nick), _logger.LogLevel.WARNING)
    _logger.log('[' + __name__ + '] User {0} created: {1}, last login: {2}, last ip: {3}, total connections: {4}'.format(
        user_nick,created_iso,lastconnected_iso,user_lastip,user_conns
    ), _logger.LogLevel.WARNING)


    # remove orphan ts3 users

    #return

    try:
        # Note, that the client will wait for the response and raise a
        # **TS3QueryError** if the error id of the response is not 0.
        ts3conn = ts3.query.TS3Connection(_ts3.TS_HOST)
        ts3conn.login(
            client_login_name=_ts3.TS_USER,
            client_login_password=_ts3.TS_PASSWORD
        )
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] unable to connect to TS3: "{0}"'.format(err.resp.error["msg"]),_logger.LogLevel.ERROR)
        return

    ts3conn.use(sid=_ts3.TS_SERVER_ID)

    try:
        resp = ts3conn.clientdbdelete(cldbid=ts3_userid)
        _logger.log('[' + __name__ + '] ts3 user {0} removed'.format(user_nick),_logger.LogLevel.WARNING)
    except ts3.query.TS3QueryError as err:
        _logger.log('[' + __name__ + '] ts3 error: "{0}"'.format(err),_logger.LogLevel.WARNING)

    # client removed. gg.

    return
