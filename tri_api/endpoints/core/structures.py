from flask import Flask, json, request, Response
from tri_api import app
from joblib import Parallel, delayed
from common.check_role import check_role
from concurrent.futures import ThreadPoolExecutor, as_completed
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers

import common.request_esi

@app.route('/core/<charid>/structures', methods=['GET'])
def core_structures(charid):


    # get all the structure shit for the char in question

    # check that the user has the right roles (to make the esi endpoint work)

    allowed_roles = ['Director', 'Station_Manager']
    code, result = check_role(__name__, charid, allowed_roles)

    if code == 'error':
        error = 'unable to check character roles for {0}: ({1}) {2}'.format(charid, code, result)
        _logger.log('[' + __name__ + ']' + error,_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp
    elif code == False:
        error = 'insufficient corporate roles to access this endpoint.'
        _logger.log('[' + __name__ + '] ' + error,_logger.LogLevel.INFO)
        js = json.dumps({ 'error': error})
        resp = Response(js, status=403, mimetype='application/json')
        return resp
    else:
        _logger.log('[' + __name__ + '] sufficient roles to view corp structure information',_logger.LogLevel.DEBUG)

    # get corpid

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=['uid', 'corporation']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + function + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return None

    if result == None:
        msg = 'uid {0} not in ldap'.format(uid)
        _logger.log('[' + function + '] {}'.format(msg),_logger.LogLevel.DEBUG)
        return None
    (dn, info), = result.items()

    corpid = info.get('corporation')

    esi_url = 'corporations/' + str(corpid)
    esi_url = esi_url + '/structures'

    # get all structures that this user has access to

    code, result_parsed = common.request_esi.esi(__name__, esi_url, 'get', charid=charid)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /structures API error ' + str(code) + ': ' + str(result_parsed['error']), _logger.LogLevel.ERROR)
        resp = Response(result_parsed['error'], status=code, mimetype='application/json')
        return resp

    _logger.log('[' + __name__ + '] /structures output:'.format(result_parsed), _logger.LogLevel.DEBUG)

    try:
        errormsg = result_parsed['error']
        resp = Response(errormsg, status=403, mimetype='application/json')
        return resp
    except Exception:
        pass

    # get name of structures and build the structure dictionary

    structures = dict()

    with ThreadPoolExecutor(10) as executor:
        futures = { executor.submit(structure_parse, charid, object, object['structure_id']): object for object in result_parsed }
        for future in as_completed(futures):
            structure_id = futures[future]['structure_id']
            data = future.result()
            structures[structure_id] = data
    js = json.dumps(structures)
    resp = Response(js, status=200, mimetype='application/json')
    return resp

def structure_parse(charid, object, structure_id):

    import common.logger as _logger
    import common.database as DATABASE
    import common.request_esi
    import json

    from datetime import datetime, timedelta

    structure = {}
    structure_id = int(structure_id)

    try:
        structure['fuel_expires'] = object['fuel_expires']
    except:
        # there seems to be no fuel key if there are no services
        # unclear on what happens if there are services but no fuel
        structure['fuel_expires'] = 'Unknown'

    structure['structure_id'] = structure_id

    # build vulnerability timers
    # monday is day 0 according to swagger spec

    today = datetime.today().weekday()
    _offsets = (3, 1, 1, 1, 1, 1, 2)

    start = datetime.now()
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start - timedelta(days=_offsets[today])
    vuln_dates = []
    for moment in object['current_vul']:
        hour = moment['hour']
        day = moment['day']
        window = start + timedelta(days=day, hours=hour)
        window = window.strftime("%Y-%m-%d %H:%M:%S")
        vuln_dates.append(window)

    structure['vuln_dates'] = vuln_dates
    esi_url = 'universe/structures/' + str(structure_id)
    esi_url = esi_url + ''

    code, data = common.request_esi.esi(__name__, esi_url, method='get', charid=charid)
    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /structures API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.ERROR)

    # catch errors

    try:
        structure['name'] = data['name']
    except:
        # try a graceful fail
        structure['name'] = 'Unknown'
        structure['system'] = 'Unknown'
        structure['region'] = 'Unknown'
        error = data['error']
        error_code = data['code']
        return structure

    # get structure type name

    typeid = data['type_id']
    esi_url = 'universe/types/{0}'.format(typeid)
    esi_url = esi_url + ''

    code, typedata = common.request_esi.esi(__name__, esi_url, 'get')
    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /universe/types API error ' + str(code) + ': ' + str(typedata['error']), _logger.LogLevel.ERROR)

    try:
        structure['type_name'] = typedata['name']
    except:
        structure['type_name'] = 'Unknown'
        return structure


    # get solar system info
    # step 1: get name and constellation

    system_id = data['solar_system_id']
    esi_url = 'universe/systems/{0}/'.format(system_id)
    esi_url = esi_url + ''

    code, data = common.request_esi.esi(__name__, esi_url, 'get')
    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /universe/systems API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.ERROR)
        resp = Response(result['error'], status=code, mimetype='application/json')
        return resp

    try:
        constellation_id = data['constellation_id']
        structure['system'] = data['name']
    except:
        structures[structure_id] = structure
        error = data['error']
        error_code = data['code']
        return structure

    # step 2: get the constellation info

    esi_url = 'universe/constellations/{0}'.format(constellation_id)
    esi_url = esi_url + ''

    code, data = common.request_esi.esi(__name__, esi_url, 'get')
    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /universe/constellations API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.ERROR)
        resp = Response(result['error'], status=code, mimetype='application/json')
        return resp

    try:
        region_id = data['region_id']
    except:
        structures[structure_id] = structure
        error = data['error']
        error_code = data['code']
        return structure

    # step 3: get region name
    esi_url = 'universe/regions/{0}/'.format(region_id)
    esi_url = esi_url + ''

    code, data = common.request_esi.esi(__name__, esi_url, 'get')
    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /universe/regions API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.ERROR)
        resp = Response(result['error'], status=code, mimetype='application/json')
        return resp

    try:
        structure['region'] = data['name']
    except:
        structures[structure_id] = structure
        error = data['error']
        error_code = data['code']
        return structure

    return structure
