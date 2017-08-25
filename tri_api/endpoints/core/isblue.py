from flask import Flask, request, url_for, json, Response
from tri_api import app
import common.ldaphelpers as _ldaphelpers
import common.request_esi
import common.logger as _logger
from tri_core.common.testing import vg_alliances

@app.route('/core/<charid>/isblue', methods=['GET'])
def core_char_isblue(charid):

    # query ldap first

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'uid={}'.format(charid)
    attributes = ['accountStatus']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        msg = 'unable to connect to ldap'
        _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    # if ldap says you are blue, that is sufficient.

    if result is not None:

        (dn, info), = result.items()

        status = info['accountStatus']

        if status == 'blue':
            js = json.dumps( { 'code': 1 } )
        else:
            # not blue
            js = json.dumps( { 'code': 0 } )

        resp = Response(js, status=200, mimetype='application/json')
        return resp

    # test character
    code, result = test_char(charid)
    resp = Response(json.dumps(result), status=code, mimetype='application/json')
    return resp

@app.route('/core/isblue', methods=['GET'])
def core_isblue():

    # core isblue function that tells whether a user, corp, or alliance is currently blue to triumvirate
    _logger.log('[' + __name__ + '] testing {0}'.format(request.args['id']), _logger.LogLevel.DEBUG)

    if 'id' not in request.args:
        _logger.log('[' + __name__ + '] no id', _logger.LogLevel.WARNING)
        js = json.dumps({ 'error': 'need an id to check'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    # filtering garbage requires exception catching, as it turns out...

    try:
        id = int(request.args['id'])
    except ValueError:
        _logger.log('[' + __name__ + '] invalid id: "{0}"'.format(request.args['id']), _logger.LogLevel.WARNING)
        js = json.dumps({ 'error': 'id parameter must be integer'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    # query ldap first

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'uid={}'.format(id)
    attributes = ['accountStatus']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        msg = 'unable to connect to ldap'
        _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    # if ldap says you are blue, that is sufficient.


    if result is not None:

        (dn, info), = result.items()

        status = info['accountStatus']

        if status == 'blue':
            js = json.dumps( { 'code': 1 } )
        else:
            # not blue
            js = json.dumps( { 'code': 0 } )

        resp = Response(js, status=200, mimetype='application/json')
        return resp


    # past here, you have no status in the system so we have to hit ESI

    # query esi to determine id type and proceed accordingly

    request_url = 'universe/names/?datasource=tranquility'
    data = '[{}]'.format(id)
    _logger.log('[' + __name__ + '] determining type of id {0}'.format(id),_logger.LogLevel.DEBUG)
    code, result = common.request_esi.esi(__name__, request_url, method='post', data=data)
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get id type information for {0}: {1}'.format(id, result),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': result })
        resp = Response(js, status=code, mimetype='application/json')
        return resp

    category = result[0]['category']
    _logger.log('[' + __name__ + '] id {0} is category type: {1}'.format(id, category),_logger.LogLevel.DEBUG)

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

    import common.request_esi
    import common.logger as _logger

    # get character affiliations

    # character info

    request_url = 'characters/{0}/?datasource=tranquility'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v4')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get character info for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return(False, 'error')

    charname = result['name']
    corpid = result.get('corporation_id')

    # alliance id, if any
    request_url = 'corporations/{0}/?datasource=tranquility'.format(corpid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v3')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get character info for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return(False, 'error')

    allianceid = result.get('alliance_id')

    if allianceid is None:
        # no alliance no blue
        result = { 'code': 0 }
        return 200, result

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

    import common.request_esi
    import common.logger as _logger

    # if it is a corp it is not directly in our blue table. check its alliance.

    esi_url = 'corporations/' + str(corpid) + '/?datasource=tranquility'

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
    if allianceid == 99003916:
        result = { 'code': 1 }
        return 200, result

    # hardcode handling for noobcorps
    if allianceid is 0 or None:
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

