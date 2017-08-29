import json
import MySQLdb as mysql
import common.database as _database
import common.ldaphelpers as _ldaphelpers
import common.logger as _logger
import common.request_esi

def vg_alliances():
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
        query = 'SELECT allianceID FROM Permissions'
        cursor.execute(query)
    except Exception as errmsg:
        _logger.log('[' + __name__ + '] mysql error: ' + str(errmsg), _logger.LogLevel.ERROR)

    alliances = []

    for item, in cursor.fetchall():
        alliances.append(item)

    cursor.close()
    sql_conn.close()

    return alliances

def vg_blues():
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
        query = 'SELECT allianceID FROM BluePermissions'
        cursor.execute(query)
    except Exception as errmsg:
        _logger.log('[' + __name__ + '] mysql error: ' + str(errmsg), _logger.LogLevel.ERROR)

    alliances = []

    for item, in cursor.fetchall():
        alliances.append(item)

    cursor.close()
    sql_conn.close()

    return alliances

def permissions(alliance_id):

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
