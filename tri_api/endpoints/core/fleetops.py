from flask import request
from tri_api import app

@app.route('/core/fleets/opsboard/<int:char_id>/', methods=['GET'])
def core_fleets(char_id):
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

    query = 'SELECT idCoreOpsBoard,Time,FC,Type,Doctrine,Hype,PostedBy,Scope,authgroup FROM OpsBoard WHERE Time > NOW() ORDER BY Time ASC'
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

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'uid={}'.format(char_id)
    attributes = ['corporation', 'authGroup', 'characterName', 'corporationName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        msg = 'unable to connect to ldap'
        _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
        js = json.dumps({'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result is not None:

        (dn, info), = result.items()

        name = info['characterName']
        groups = info['authGroup']
        corp = int(info['corporation'])
        corpName = info['corporationName']

        fleets = []

        for row in rows:

            fleet_type = row[3]

            if fleet_type == "THIRD PARTY FIGHT":
                fleet_type = "FLEET"

            fleet = {
                'id': row[0],
                'time': row[1].isoformat(),
                'fc': row[2],
                'type': fleet_type,
                'doctrine': row[4],
                'text': row[5],
                'by': row[6],
                'modifiable': False
            }

            if 'skyteam' in groups:
                fleet['modifiable'] = True
            elif name == row[6]:
                fleet['modifiable'] = True

            scope = int(row[7])

            if scope == 1 and 'vanguard' in groups:
                fleet['group'] = 'vanguard'
                fleets.append(fleet)
            elif scope == 2 and 'triumvirate' in groups:
                fleet['group'] = 'triumvirate'
                fleets.append(fleet)
            elif scope == corp:
                fleet['group'] = corpName
                fleets.append(fleet)
        return Response(json.dumps(fleets), status=200, mimetype='application/json')
    else:
        return Response({'error': 'not found'}, status=404, mimetype='application/json')


@app.route('/core/fleets/opsboard/past/<int:char_id>/', methods=['GET'])
def core_fleets_past(char_id):
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

    query = 'SELECT idCoreOpsBoard,Time,FC,Type,Doctrine,Hype,PostedBy,Scope,authgroup FROM OpsBoard WHERE Time < NOW() ORDER BY Time DESC limit 10'
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

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'uid={}'.format(char_id)
    attributes = ['corporation', 'authGroup', 'characterName', 'corporationName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        msg = 'unable to connect to ldap'
        _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
        js = json.dumps({'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result is not None:

        (dn, info), = result.items()

        name = info['characterName']
        groups = info['authGroup']
        corp = int(info['corporation'])
        corpName = info['corporationName']

        fleets = []

        for row in rows:

            fleet_type = row[3]

            if fleet_type == "THIRD PARTY FIGHT":
                fleet_type = "FLEET"

            fleet = {
                'id': row[0],
                'time': row[1].isoformat(),
                'fc': row[2],
                'type': fleet_type,
                'doctrine': row[4],
                'text': row[5],
                'by': row[6],
                'modifiable': False
            }
            scope = int(row[7])

            if scope == 1 and 'vanguard' in groups:
                fleet['group'] = 'vanguard'
                fleets.append(fleet)
            elif scope == 2 and 'triumvirate' in groups:
                fleet['group'] = 'triumvirate'
                fleets.append(fleet)
            elif scope == corp:
                fleet['group'] = corpName
                fleets.append(fleet)
        return Response(json.dumps(fleets), status=200, mimetype='application/json')
    else:
        return Response({'error': 'not found'}, status=404, mimetype='application/json')
