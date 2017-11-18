from flask import Flask, json, request, Response
from tri_api import app
from joblib import Parallel, delayed
from common.check_role import check_role
from concurrent.futures import ThreadPoolExecutor, as_completed
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.request_esi
import time
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from tri_core.common.moonprices import moon_typedata

@app.route('/core/<charid>/structures/mining_ledger', methods=['GET'])
def core_mining_ledger(charid):

    # locate all active moon mining structures

    allowed_roles = ['Director', 'Accountant']
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
        _logger.log('[' + __name__ + '] sufficient roles to view corp mining structure information',_logger.LogLevel.DEBUG)

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


    # fetch all moon mining structure ids

    request_url = 'corporation/{0}/mining/observers/'.format(corpid)
    code, result_parsed = common.request_esi.esi(__name__, request_url, 'get', version='v1', charid=charid)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /mining/observers API error ' + str(code) + ': ' + str(result_parsed['error']), _logger.LogLevel.ERROR)
        resp = Response(result_parsed['error'], status=code, mimetype='application/json')
        return resp

    _logger.log('[' + __name__ + '] /mining/observers output:'.format(result_parsed), _logger.LogLevel.DEBUG)

    try:
        errormsg = result_parsed['error']
        resp = Response(errormsg, status=403, mimetype='application/json')
        return resp
    except Exception:
        pass

    # get name of structures and build the structure dictionary

    structures = dict()
    moon_ores_byname, moon_ores_bytype = moon_typedata()

    with ThreadPoolExecutor(10) as executor:
        futures = { executor.submit(ledger_parse, moon_ores_bytype, charid, corpid, object, object['observer_id']): object for object in result_parsed }
        for future in as_completed(futures):
            data = future.result()
            structure_id = data.get('structure_id')
            structures[structure_id] = data
    js = json.dumps(structures)
    resp = Response(js, status=200, mimetype='application/json')
    return resp

def ledger_parse(moon_data, charid, corpid, object, structure_id):

    import common.logger as _logger
    import common.request_esi
    import json

    # for each moon mining structure, parse the ledger.

    # moon mining typeids

    # goo bearing ores including jackpots

    ubiquitous = list(range(45490, 45494)) + list(range(46280, 46287))
    common_ore = list(range(45494, 45498)) + list(range(46288, 46296))
    uncommon = list(range(45498, 45502)) + list(range(46296, 46303))
    rare = list(range(45502, 45507)) + list(range(46304, 46312))
    exceptional = list(range(45510, 45514)) + list(range(46312, 46320))

    # standard +15% ore varieties

    standard = list(range(46675, 46690))

    taxable = ubiquitous + common_ore + uncommon + rare + exceptional
    all_ores = standard + taxable

    structure = { 'structure_id': structure_id }

    request_url = 'universe/structures/{0}/'.format(structure_id)
    code, data = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /structures API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.ERROR)
        structure['name'] = 'Unknown'
        structure['system'] = 'Unknown'
        structure['region'] = 'Unknown'
        error = data['error']
        print(data)
        error_code = code
        return structure

    structure['name'] = data.get('name')
    structure['solar_system_id'] = data.get('solar_system_id')
    structure['type_id'] = data.get('type_id')
    structure['position'] = data.get('position')

    # get structure type name

    typeid = data['type_id']
    esi_url = 'universe/types/{0}'.format(typeid)
    esi_url = esi_url + '?datasource=tranquility'

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

    structure['system_info'] = common.esihelpers.solar_system_info(data.get('solar_system_id'))

    # get mining ledger

    request_url = 'corporation/{0}/mining/observers/{1}/'.format(corpid, structure_id)
    code, data = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /mining/observers API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.ERROR)
        structure['ledger'] = None
        error = data['error']
        return structure

    raw_ledger = data
    last_month = datetime.now() - relativedelta(months=1)
    this_month = datetime.now()

    last_month = last_month.month
    this_month = this_month.month

    this_month_total_value = 0
    last_month_total_value = 0

    this_month_taxable_value = 0
    last_month_taxable_value = 0

    ores = {}

    for item in raw_ledger:

        taxed_value = 0
        total_value = 0


        miner = item.get('character_id')
        miner_corpid = item.get('recorded_corporation_id')
        mined_typeid = item.get('type_id')
        mined_amount = item.get('quantity')
        mined_typeid_data = moon_data[mined_typeid]


        try:
            last_updated = parse(item.get('last_updated'))
        except Exception:
            msg = 'unable to process mining ledger for corp {0}. badly formatted time: {1}'.format(corpid, item.get('last_updated'))
            _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.WARNING)
            continue

        mined_value = mined_amount * mined_typeid_data['unit_value']
        total_value += mined_value

        if ores.get(mined_typeid) is None:
            ores[mined_typeid] = { 'quantity': 0, 'taxable': False, 'name': mined_typeid_data['name'] }

        if mined_typeid in taxable:
            taxed_value = mined_value
            ores[mined_typeid]['taxable'] = True

        ores[mined_typeid]['quantity'] += mined_amount

        # we care about two months: this month, and last month.

        if last_updated.month == last_month:
            last_month_taxable_value += taxed_value
            last_month_total_value += total_value

        if last_updated.month == this_month:
            this_month_taxable_value += taxed_value
            this_month_total_value += total_value

    this_month_total_value = round(this_month_total_value, 2)
    this_month_taxable_value = round(this_month_taxable_value, 2)

    last_month_total_value = round(last_month_total_value, 2)
    last_month_taxable_value = round(last_month_taxable_value, 2)


    ledger = {
        'this_month': { 'total': this_month_total_value, 'taxable': this_month_taxable_value },
        'last_month': { 'total': last_month_total_value, 'taxable': last_month_taxable_value },
    }

    structure['ores'] = ores
    structure['ledger'] = ledger

    return structure
