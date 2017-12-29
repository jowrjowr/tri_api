from flask import Flask, json, request, Response
from tri_api import app
from joblib import Parallel, delayed
from common.check_role import check_role
from concurrent.futures import ThreadPoolExecutor, as_completed
import MySQLdb as mysql
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.request_esi
import time
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from tri_core.common.moonprices import moon_typedata
from tri_core.common.testing import vg_renters

@app.route('/core/command/structures/mining_ledger', methods=['GET'])
def command_mining_ledger():

    # process mining ledger as a command level view

    log_address = request.args.get('log_ip')
    log_charid = request.args.get('log_charid')
    msg = 'command mining ledger view'

    _logger.securitylog(__name__, msg, ipaddress=log_address, charid=log_charid)

    # fetch the common moon pricing data

    _, moon_data = moon_typedata()

    # the following alliances are taxed on moon miner ownership

    taxed_alliances = vg_renters() + [ 933731581 ]

    # process all the alliances and each corp within them

    command_ledger = dict()
    ledger_characters = list()

    for alliance in taxed_alliances:

        request_url = 'alliances/{0}/corporations/'.format(alliance)
        code, result = common.request_esi.esi(__name__, request_url, 'get', version='v1')

        if not code == 200:
            # something broke severely
            _logger.log('[' + __name__ + '] /alliances/{0}/corporations API error {1}: {2}'.format(alliance, code, result['error']), _logger.LogLevel.ERROR)
            resp = Response(result['error'], status=code, mimetype='application/json')
            return resp

        msg = '/alliances/{0}/corporations output: {1}'.format(alliance, result)
        _logger.log('[' + __name__ + '] /mining/observers output: '.format(result), _logger.LogLevel.DEBUG)

        for corporation in result:
            # fetch a character per-corp that can fetch the mining ledger data

            corporation = int(corporation)

            # get the corp name

            request_url = 'corporations/{0}/'.format(corporation)
            code, result = common.request_esi.esi(__name__, request_url, method='get', version='v4')
            if not code == 200:
                corpname = 'Unknown'
            else:
                corpname = result.get('name')

            command_ledger[corporation] = {
                'corpid': corporation,
                'corpname': corpname,
                'moons': 0,
                'this_month': 0,
                'last_month': 0,
                'token': False,
            }

            mining_scope = 'esi-industry.read_corporation_mining.v1'

            dn = 'ou=People,dc=triumvirate,dc=rocks'
            filterstr='(&(corporation={0})(esiScope={1})(corporationRole=Director)(esiAccessToken=*))'.format(corporation, mining_scope)
            attrlist=[ 'uid' ]
            code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

            print(code, result)

            if code == False:
                msg = 'unable to fetch ldap information: {}'.format(error)
                _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
                resp = Response(msg, status=500, mimetype='application/json')
                return resp

            if result is None:
                # no compatible token, for whatever reason. no ledger.
                command_ledger[corporation]['token'] = False
                continue
            else:
                # has a token
                command_ledger[corporation]['token'] = True

            # grab the first compatible token. it literally doesn't matter which.
            # dictionaries are explicitly unordered though!

            user = next(iter(result))
            charid = result[user]['uid']
            msg = 'using {0} ({1}) for checking corp {2}'.format(user, charid, corporation)

            # TODO: REMOVE DEBUG
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)

            ledger_characters.append(charid)

    with ThreadPoolExecutor(15) as executor:
        futures = { executor.submit(mining_ledger, moon_data, charid): charid for charid in ledger_characters }
        for future in as_completed(futures):
            code, result = future.result()

            if code is not True:
                continue

            for structure_id in result:

                try:
                    data = result[structure_id]
                except Exception as e:
                    print(structure_id)
                    continue
                # fetch the actual ledger data

                last_month = data['ledger']['last_month']['taxable']
                this_month = data['ledger']['this_month']['taxable']
                corpid = int(data['corpid'])
                corpname = data['corpname']

                # there ought to already be ledger data. add to it.

                command_ledger[corpid]['moons'] += 1
                command_ledger[corpid]['this_month'] += this_month
                command_ledger[corpid]['last_month'] += last_month

    js = json.dumps(command_ledger)
    return Response(js, status=200, mimetype='application/json')

@app.route('/core/<charid>/structures/mining_ledger', methods=['GET'])
def core_mining_ledger(charid):


    allowed_roles = ['Director', 'Accountant']
    code, result = check_role(__name__, charid, allowed_roles)

    if code == 'error':
        error = 'unable to check character roles for {0}: ({1}) {2}'.format(charid, code, result)
        _logger.log('[' + __name__ + ']' + error, _logger.LogLevel.ERROR)
        resp = Response(error, status=500, mimetype='application/json')
    elif code == False:
        error = 'insufficient corporate roles to access this endpoint.'
        _logger.log('[' + __name__ + '] ' + error,_logger.LogLevel.INFO)
        resp = Response(error, status=500, mimetype='application/json')
    else:
        _logger.log('[' + __name__ + '] sufficient roles to view corp mining structure information',_logger.LogLevel.DEBUG)

    # moon mining data
    _, moon_data = moon_typedata()

    # wrapper around the ledger function for flask

    code, result = mining_ledger(moon_data, charid)

    if code is True:
        js = json.dumps(result)
        resp = Response(js, status=200, mimetype='application/json')
    else:
        js = json.dumps({ 'error': result })
        resp = Response(js, status=500, mimetype='application/json')

    return resp

def mining_ledger(moon_data, charid):

    # process mining ledger for taxes for a corp

    # get corpid

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=[ 'uid', 'corporation', 'corporationName' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return False, msg

    if result == None:
        msg = 'uid {0} not in ldap'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)
        return False, msg
    (dn, info), = result.items()

    corpid = info.get('corporation')
    corpname = info.get('corporationName')

    # fetch all moon mining structure ids

    request_url = 'corporation/{0}/mining/observers/'.format(corpid)
    code, result_parsed = common.request_esi.esi(__name__, request_url, 'get', version='v1', charid=charid)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /mining/observers API error ' + str(code) + ': ' + str(result_parsed['error']), _logger.LogLevel.ERROR)
        return False, result_parsed['error']

    _logger.log('[' + __name__ + '] /mining/observers output:'.format(result_parsed), _logger.LogLevel.DEBUG)

    try:
        errormsg = result_parsed['error']
        return False, errormsg
    except Exception:
        pass

    # get name of structures and build the structure dictionary

    structures = dict()

    with ThreadPoolExecutor(10) as executor:
        futures = { executor.submit(ledger_parse, moon_data, charid, corpid, object, object['observer_id']): object for object in result_parsed }
        for future in as_completed(futures):
            data = future.result()
            data['corpname'] = corpname
            structure_id = data.get('structure_id')
            structures[structure_id] = data

    return True, structures

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
        error_code = code
        return structure

    structure['name'] = data.get('name')
    structure['solar_system_id'] = data.get('solar_system_id')
    structure['type_id'] = data.get('type_id')
    structure['position'] = data.get('position')
    structure['corpid'] = corpid

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

    # build ledger, but scale by billion isk as well

    billion = 1000000000

    this_month_total_value = round(this_month_total_value / billion, 2)
    this_month_taxable_value = round(this_month_taxable_value / billion, 2)

    last_month_total_value = round(last_month_total_value / billion, 2)
    last_month_taxable_value = round(last_month_taxable_value / billion, 2)


    ledger = {
        'this_month': { 'total': this_month_total_value, 'taxable': this_month_taxable_value },
        'last_month': { 'total': last_month_total_value, 'taxable': last_month_taxable_value },
    }

    structure['ores'] = ores
    structure['ledger'] = ledger

    return structure
