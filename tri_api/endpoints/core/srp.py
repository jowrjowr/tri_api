from flask import request
from tri_api import app

@app.route('/core/srp/requests/<int:char_id>/', methods=['GET'])
def core_srp_requests(char_id):
    from flask import Response, request
    from json import dumps

    import common.logger as _logger
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import MySQLdb as mysql
    import json

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        js = json.dumps({'error': str(err)})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    cursor = sql_conn.cursor()

    query = 'SELECT RequestTime, LossTime, charName, zkbLink, ShipType, estPayout FROM SRP WHERE RequestedByCharID = {0} AND srpStatus = 0'.format(char_id)
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        js = json.dumps({'error': str(err)})
        resp = Response(js, status=500, mimetype='application/json')
        return resp
    finally:
        cursor.close()

    requests = []

    for row in rows:
        requests.append({
            'date': row[0],
            'km_date': row[1],
            'character_name': row[2],
            'zkb': row[3],
            'ship': row[4],
            'payout': row[5]
        })

    return Response(json.dumps(requests), status=200, mimetype='application/json')


@app.route('/core/srp/requests/<int:char_id>/past/', methods=['GET'])
def core_srp_requests_past(char_id):
    from flask import Response, request
    from json import dumps

    import common.logger as _logger
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import MySQLdb as mysql
    import json

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        js = json.dumps({'error': str(err)})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    cursor = sql_conn.cursor()

    query = 'SELECT srpStatus, RequestTime, LossTime, charName, zkbLink, DenyReason, ShipType, estPayout   FROM SRP WHERE RequestedByCharID = {0} AND srpStatus <> 0'.format(char_id)
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        js = json.dumps({'error': str(err)})
        resp = Response(js, status=500, mimetype='application/json')
        return resp
    finally:
        cursor.close()

    requests = []

    for row in rows:
        requests.append({
            'status': row[0],
            'date': row[1],
            'km_date': row[2],
            'character_name': row[3],
            'zkb': row[4],
            'reason': row[6],
            'ship': row[6],
            'payout': row[7]
        })

    return Response(json.dumps(requests), status=200, mimetype='application/json')