def core_isblue():

    from flask import Flask, request, url_for, json, Response
    from common.api import base_url
    import common.request_esi
    import common.logger as _logger
    import requests
    import json

    # core isblue function that tells whether a user, corp, or alliance is currently blue to triumvirate
    _logger.log('[' + __name__ + '] testing {0}'.format(request.args['id']), _logger.LogLevel.DEBUG)

    if 'id' not in request.args:
        _logger.log('[' + __name__ + '] no id', _logger.LogLevel.WARNING)
        js = json.dumps({ 'code': 500, 'error': 'need an id to check'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    # filtering garbage requires exception catching, as it turns out...

    try:
        id = int(request.args['id'])
    except ValueError:
        _logger.log('[' + __name__ + '] invalid id: "{0}"'.format(request.args['id']), _logger.LogLevel.WARNING)
        js = json.dumps({ 'code': 500, 'error': 'id parameter must be integer'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    # query esi to determine id type and proceed accordingly

    request_url = base_url + 'universe/names/?datasource=tranquility'
    data = '[{}]'.format(id)
    _logger.log('[' + __name__ + '] determining type of id {0}'.format(id),_logger.LogLevel.DEBUG)
    code, result = common.request_esi.esi(__name__, request_url, 'post', data)
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get id type information for {0}: {1}'.format(id, result['error']),_logger.LogLevel.ERROR)
        js = json.dumps({ 'code': code, 'error': result['error'] })
        resp = Response(js, status=code, mimetype='application/json')
        return resp

    category = result[0]['category']
    _logger.log('[' + __name__ + '] id {0} is category type: {1}'.format(id, category),_logger.LogLevel.INFO)

    if category == 'alliance':
        # test alliance
        code, result = test_alliance(id)
        resp = Response(json.dumps(result), status=code, mimetype='application/json')
        return resp
    elif category == 'corporation':
        # test corporation  
        code, result = test_corp(id)
        resp = Response(json.dumps(result), status=code, mimetype='application/json')
        return resp
    elif category == 'character':
        # test character
        code, result = test_char(id)
        resp = Response(json.dumps(result), status=code, mimetype='application/json')
        return resp
    else:
        # unknown category
        code = 404
        result = {'code': 0, 'error': "unknown id category"}
        resp = Response(json.dumps(result), status=code, mimetype='application/json')
        return resp

def test_char(charid):

    from common.api import base_url
    import common.request_esi
    import common.logger as _logger

    # get character affiliations
    request_url = base_url + 'characters/affiliation/?datasource=tranquility'
    data = '[{}]'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, 'post', data)
    _logger.log('[' + __name__ + '] affiliations output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] affiliations API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        error = result['error']
        result = { 'code': code, 'error': error }
        return code, result
        
    corpid = result[0]['corporation_id']
    try:
        allianceid = result[0]['alliance_id']
    except KeyError:
        allianceid = 0
    
    # test the character's corporation
    
    code, result = test_corp(corpid)
    if not code == 200:
        # something broke severely
        error = result['error']
        _logger.log('[' + __name__ + '] error testing corp {0} for charid {1}: {2}'.format(corpid, charid, error), _logger.LogLevel.ERROR)
        result = { 'code': code, 'error': error }
        return code, result
    
    if result['code'] == 1:
        # the direct corporation test is passed
        return 200, result

    # test the character's alliance
    code, result = test_alliance(allianceid)
    if not code == 200:
        # something broke severely
        error = result['error']
        _logger.log('[' + __name__ + '] error testing alliance {0} for charid {1}: {2}'.format(allianceid, charid, error), _logger.LogLevel.ERROR)
        result = { 'code': code, 'error': error }
        return code, result
        
    if result['code'] == 1:
        # the direct corporation test is passed
        return 200, result
        
    # failed corp and alliance level testing. not blue.
    result = { 'code': 0 }
    return 200, result
    
def test_corp(corpid):

    # everything for testing if this is a corp and if the corp / parent
    # alliance are blue to us

    from common.api import base_url
    import common.request_esi
    import common.logger as _logger

    # if it is a corp it is not directly in our blue table. check its alliance.

    esi_url = base_url + 'corporations/' + str(corpid) + '/?datasource=tranquility'

    # do the request, but catch exceptions for connection issues

    code, result = common.request_esi.esi(__name__, esi_url, 'get')
    _logger.log('[' + __name__ + '] /corporations output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /corporations API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        error = result['error']
        result = { 'code': code, 'error': error }
        return code, result

    try:
        alliance_id = result['alliance_id']
    except KeyError:
        # no alliance id. not blue.
        result = { 'code': 0 }
        return 200, result
    # test the alliance id
    code, result = test_alliance(alliance_id)

    return code, result

def test_alliance(allianceid):

    import MySQLdb as mysql
    import common.credentials.database as _database
    import common.logger as _logger

    # hard code for viral society alt alliance
    if id == 99003916:
        result = { 'code': 1 }
        return 200, result

    # hardcode handling for noobcorps
    if id == 0:
        result = { 'code': 0 }
        return 200, result

    # attempt mysql connection (abort in case of failure)
    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        result = { 'code': 500, 'error': 'unable to connect to mysql: ' + str(err)}
        return 500, result
    
    # check the alliance id against the blue list

    cursor = sql_conn.cursor()
    query = 'SELECT allianceID,allianceName FROM Permissions WHERE allianceID = %s'
    try:
        row = cursor.execute(query, (allianceid,))
        cursor.close()
    except Exception as errmsg:
        result = { 'code': 500, 'error': 'mysql broke: ' + str(errmsg)}
        _logger.log('[' + __name__ + '] mysql error: ' + str(errmsg), _logger.LogLevel.ERROR)
        return 500, result
    if row == 1:
        result = { 'code': 1 }
        return 200, result

    # not blue 
    result  = { 'code': 0 }
    return 200, result

