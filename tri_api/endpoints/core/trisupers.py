from flask import request, Response, json
from tri_api import app
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.check_role import check_role
import common.request_esi
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
from common.logger import getlogger_new as getlogger
from common.logger import securitylog_new as securitylog


@app.route('/core/trisupers/', methods=[ 'GET' ])
def core_trisupers():

    # logging

    logger = getlogger('core.trisupers')

    ipaddress = request.args.get('log_ip')
    if ipaddress is None:
        ipaddress = request.headers['X-Real-Ip']

    charid = request.args.get('charid')

    if charid is None:
        error = 'need a charid to authenticate with'
        js = json.dumps({'error': error})
        resp = Response(js, status=405, mimetype='application/json')
        return resp

    securitylog('supers audit', ipaddress=ipaddress, charid=charid)

    # check for auth groups

    allowed_roles = ['tsadmin']
    dn = 'ou=People,dc=triumvirate,dc=rocks'

    code, result = _ldaphelpers.ldap_search(__name__, dn, '(uid={})'.format(charid), ['authGroup'])

    if code == 'error':
        error = 'unable to check auth groups roles for {0}: ({1}) {2}'.format(charid, code, result)
        logger.error(error)
        js = json.dumps({'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        logger.error(msg)
        js = json.dumps({'error': msg})
        return Response(js, status=404, mimetype='application/json')

    (_, result), = result.items()

    if not "command" in result['authGroup']:
        error = 'insufficient authgroup privileges to access this endpoint.'
        logger.error(error)
        js = json.dumps({'error': error})
        resp = Response(js, status=403, mimetype='application/json')
        return resp

    # get people in trisupers

    pilots = []

    filterstr = '(&(esiAccessToken=*)(alliance=933731581)(authGroup=trisupers))'
    attrlist = ['uid', 'corporation', 'characterName', 'altOf']

    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    for _, info in result.items():
        pilots.append(info['uid'])

    result_supers = result

    # iterate through and add each charid from registered alts

    for charid in pilots:
        filterstr = 'altOf={}'.format(charid)
        attrlist = ['uid', 'corporation', 'characterName', 'altOf']

        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)
        if result:
            result_supers = {**result_supers, **result}

    supers = dict()

    with ThreadPoolExecutor(40) as executor:
        futures = { executor.submit(audit_pilot, result_supers[cn]): cn for cn in result_supers }
        for future in as_completed(futures):
            data = future.result()

            try:
                supers.update(data)
            except Exception as err:
                msg = 'super audit for failed: {0}'.format(err)
                logger.error(msg)

    supers_cleaned = {}

    for key in supers:
        supers_cleaned[supers[key]['item_id']] = supers[key]

    js = json.dumps(supers_cleaned)
    return Response(js, status=200, mimetype='application/json')


@app.route('/core/corpsupers/', methods=['GET'])
def core_corpsupers():
    dn = 'ou=People,dc=triumvirate,dc=rocks'

    # logging

    logger = getlogger('core.corpsupers')

    ipaddress = request.args.get('log_ip')
    if ipaddress is None:
        ipaddress = request.headers['X-Real-Ip']

    charid = request.args.get('charid')

    if charid is None:
        error = 'need a charid to authenticate with'
        js = json.dumps({'error': error})
        resp = Response(js, status=405, mimetype='application/json')
        return resp

    securitylog('supers audit', ipaddress=ipaddress, charid=charid)

    # check for auth groups

    allowed_roles = ['Director', 'Personnel_Manager']
    roles = check_role(charid, allowed_roles)

    if not roles:
        return Response(json.dumps({'error': "forbidden"}), status=403, mimetype='application/json')

    # get corp

    code, result = _ldaphelpers.ldap_search(__name__, dn, '(uid={})'.format(charid), ['corporation'])

    if code == 'error':
        error = 'unable to check auth groups roles for {0}: ({1}) {2}'.format(charid, code, result)
        logger.error(msg)
        js = json.dumps({'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        logger.error(msg)
        js = json.dumps({'error': msg})
        return Response(js, status=404, mimetype='application/json')

    (_, result), = result.items()

    # get super pilots

    filterstr = '(&(esiAccessToken=*)(corporation={0}))'.format(result['corporation'])
    attrlist = ['uid', 'corporation', 'characterName', 'altOf']

    code_supers, result_supers = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    supers = dict()

    with ThreadPoolExecutor(25) as executor:
        futures = { executor.submit(audit_pilot, result_supers[cn]): cn for cn in result_supers }
        for future in as_completed(futures):
            data = future.result()

            try:
                supers.update(data)
            except Exception as err:
                msg = 'super audit for failed: {0}'.format(err)
                logger.error(msg)

    supers_cleaned = {}

    for key in supers:
        supers_cleaned[supers[key]['item_id']] = supers[key]

    js = json.dumps(supers_cleaned)
    return Response(js, status=200, mimetype='application/json')


@app.route('/core/corpcaps/', methods=['GET'])
def core_corpcapitals():
    dn = 'ou=People,dc=triumvirate,dc=rocks'
    # logging

    logger = getlogger('core.corp_capitals')
    ipaddress = request.args.get('log_ip')
    if ipaddress is None:
        ipaddress = request.headers['X-Real-Ip']

    charid = request.args.get('charid')

    if charid is None:
        error = 'need a charid to authenticate with'
        js = json.dumps({'error': error})
        resp = Response(js, status=405, mimetype='application/json')
        return resp

    securitylog('capitals audit', ipaddress=ipaddress, charid=charid)

    # check for auth groups

    allowed_roles = ['Director', 'Personnel_Manager']
    roles = check_role(charid, allowed_roles)

    if not roles:
        return Response(json.dumps({'error': "forbidden"}), status=403, mimetype='application/json')

    # get corp

    code, result = _ldaphelpers.ldap_search(__name__, dn, '(uid={})'.format(charid), ['corporation'])

    if code == 'error':
        error = 'unable to check auth groups roles for {0}: ({1}) {2}'.format(charid, code, result)
        logger.error(error)
        js = json.dumps({'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        logger.error(msg)
        js = json.dumps({'error': msg})
        return Response(js, status=404, mimetype='application/json')

    (_, result), = result.items()

    # get super pilots

    filterstr = '(&(esiAccessToken=*)(corporation={0}))'.format(result['corporation'])
    attrlist = ['uid', 'corporation', 'characterName', 'altOf']

    code_capitals, result_capitals = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    supers = dict()

    with ThreadPoolExecutor(75) as executor:
        futures = { executor.submit(audit_pilot_capitals, result_capitals[cn]): cn for cn in result_capitals }
        for future in as_completed(futures):
            data = future.result()

            try:
                supers.update(data)
            except Exception as err:
                msg = 'capital audit for failed: {0}'.format(err)
                logger.error(msg)

    supers_cleaned = {}

    for key in supers:
        supers_cleaned[supers[key]['item_id']] = supers[key]

    js = json.dumps(supers_cleaned)
    return Response(js, status=200, mimetype='application/json')


def audit_pilot(entry):

    ships = dict()
    basic_pilot = dict()

    uid = entry['uid']

    logger = getlogger('core.audit_pilot.{0}.supers'.format(uid))

    msg = 'auditing character {0} for supers'.format(uid)
    logger.debug(msg)

    corpid = entry['corporation']
    charname = entry['characterName']
    altOf = entry['altOf']
    corpid = entry['corporation']

    # data pollution fix
    if altOf == 'None': altOf = None


    basic_pilot['uid'] = uid
    basic_pilot['pilot'] = charname
    basic_pilot['valid'] = False
    basic_pilot['main_charid'] = altOf

    corp_info = _esihelpers.corporation_info(corpid)

    if corp_info is not None:
        basic_pilot['corporation'] = corp_info['name']
    else:
        basic_pilot['corporation'] = "Unknown"

    # hardcoded data for asset typeids
    titans = {
        11567: 'Avatar',
        671: 'Erebus',
        45649: 'Komodo',
        3764: 'Leviathan',
        42241: 'Molok',
        23773: 'Ragnarok',
    }
    supers = {
        23919: 'Aeon',
        22852: 'Hel',
        23913: 'Nyx',
        3514: 'Revenant',
        42125: 'Vendetta',
        23917: 'Wyvern'
    }


    # fetch current ship

    code, current_ship = _esihelpers.current_ship(uid)

    if code == False:
        return ships

    # fetch super/titan typeids out of char assets

    code, char_assets = _esihelpers.find_types(uid, list(titans) + list(supers))
    if code == False:
        return ships

    # fetch character location

    code, location = _esihelpers.char_location(uid)
    if code == False:
        return ships

    # fetch main charname, if it exists

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'uid={}'.format(altOf)
    attrlist = ['uid', 'characterName']

    if not altOf == None:
        result = _ldaphelpers.ldap_uid2name(altOf)
        if result == None:
            msg = 'failed to find main for {0}'.format(altOf)
            logger.warning(msg)
        try:
            main = result
        except:
            main = "Unknown"
    else:
        main = charname

    # does this character have a titan/super in assets?

    for asset in char_assets:
        asset_typeid = asset.get('type_id')
        asset_id = asset.get('item_id')
        if asset_typeid in list(titans) + list(supers):
            ships[asset_id] = basic_pilot
            ships[asset_id]['typeid'] = asset_typeid
            ships[asset_id]['item_id'] = asset_id
            ships[asset_id]['main_charname'] = main
            ships[asset_id]['active'] = False
            ships[asset_id]['location_id'] = asset['location_id']

            if asset['location_type'] == 'station':
                request_url = 'universe/stations/{}/'.format(asset['location_id'])
                code, result = common.request_esi.esi(__name__, request_url, method='get', version='latest')

                if code == 404:
                    ships[asset_id]['location_name'] = 'STATION NOT FOUND'
                elif code == 200:
                    ships[asset_id]['location_name'] = result['name']
                else:
                    ships[asset_id]['location_name'] = "STATION ERROR"
            elif asset['location_type'] == 'other':
                request_url = 'universe/structures/{}/'.format(asset['location_id'])
                code, result = common.request_esi.esi(__name__, request_url, method='get', version='v2',
                                                      charid=uid)

                if code == 200:
                    ships[asset_id]['location_name'] = result['name']
                elif code == 403 or code == 401:
                    ships[asset_id]['location_name'] = "CITADEL FORBIDDEN"
                elif code == 404:
                    ships[asset_id]['location_name'] = 'CITADEL NOT FOUND'
                else:
                    ships[asset_id]['location_name'] = "CITADEL ERROR"
            else:
                ships[asset_id]['location_name'] = 'TYPE UNKNOWN'

        if asset_typeid in list(supers):
            ships[asset_id]['type'] = supers[asset_typeid]
            ships[asset_id]['class'] = "Supercarrier"
        if asset_typeid in list(titans):
            ships[asset_id]['type'] = titans[asset_typeid]
            ships[asset_id]['class'] = "Titan"

    # is this character flying a titan/super?
    # this is last to override the asset search with the active super (if any)

    active_typeid = current_ship.get('ship_type_id')
    active_id = current_ship.get('ship_item_id')

    if active_typeid in list(titans) + list(supers):
        # setup basics
        ships[active_id] = basic_pilot
        ships[active_id]['typeid'] = active_typeid
        ships[active_id]['item_id'] = active_id
        ships[active_id]['main_charname'] = main
        ships[active_id]['active'] = True
        ships[active_id]['location_name'] = location['location']
        # more complex location ids and names can be filled in later?

    # actual ship specific shit
    if active_typeid in list(titans):
        ships[active_id]['type'] = titans[active_typeid]
        ships[active_id]['class'] = "Titan"

    if active_typeid in list(supers):
        ships[active_id]['type'] = supers[active_typeid]
        ships[active_id]['class'] = "Supercarrier"

    return ships


def audit_pilot_capitals(entry):

    ships = dict()
    basic_pilot = dict()

    uid = entry['uid']

    logger = getlogger('core.audit_pilot.{0}.capitals'.format(uid))
    msg = 'auditing character {0} for capitals'.format(uid)
    logger.debug(msg)

    corpid = entry['corporation']
    charname = entry['characterName']
    altOf = entry['altOf']

    # data pollution fix
    if altOf == 'None':
        altOf = None

    basic_pilot['uid'] = uid
    basic_pilot['pilot'] = charname
    basic_pilot['valid'] = False
    basic_pilot['main_charid'] = altOf

    corp_info = _esihelpers.corporation_info(corpid)

    if corp_info is not None:
        basic_pilot['corporation'] = corp_info['name']
    else:
        basic_pilot['corporation'] = "Unknown"

    # hardcoded data for asset typeids
    carriers = {
        23757: 'Archon',
        23915: 'Chimera',
        24483: 'Nidhoggur',
        23911: 'Thanatos'
    }
    dreads = {
        19724: 'Moros',
        19722: 'Naglfar',
        19726: 'Phoenix',
        19720: 'Revelation',
    }
    fax = {
        37604: 'Apostle',
        37606: 'Lif',
        37605: 'Minokawa',
        37607: 'Ninazu'
    }


    # fetch current ship

    code, current_ship = _esihelpers.current_ship(uid)

    if code == False:
        return ships

    # fetch super/titan typeids out of char assets

    code, char_assets = _esihelpers.find_types(uid, list(carriers) + list(dreads) + list(fax))
    if code == False:
        return ships

    # fetch character location

    code, location = _esihelpers.char_location(uid)
    if code == False:
        return ships

    if not altOf == None:
        result = _ldaphelpers.ldap_uid2name(altOf)
        if result == None:
            msg = 'failed to find main for {0}'.format(altOf)
            logger.warning(msg)
        try:
            main = result
        except:
            main = "Unknown"
    else:
        main = charname

    # does this character have a titan/super in assets?

    for asset in char_assets:
        asset_typeid = asset.get('type_id')
        asset_id = asset.get('item_id')
        if asset_typeid in list(carriers) + list(dreads) + list(fax):
            ships[asset_id] = basic_pilot
            ships[asset_id]['item_id'] = asset_id
            ships[asset_id]['typeid'] = asset_typeid
            ships[asset_id]['main_charname'] = main
            ships[asset_id]['active'] = False
            ships[asset_id]['location_id'] = asset['location_id']

            if asset['location_type'] == 'station':
                request_url = 'universe/stations/{}/'.format(asset['location_id'])
                code, result = common.request_esi.esi(__name__, request_url, method='get', version='latest')

                if code == 404:
                    ships[asset_id]['location_name'] = 'STATION NOT FOUND'
                elif code == 200:
                    ships[asset_id]['location_name'] = result['name']
                else:
                    ships[asset_id]['location_name'] = "STATION ERROR"
            elif asset['location_type'] == 'other':
                request_url = 'universe/structures/{}/'.format(asset['location_id'])
                code, result = common.request_esi.esi(__name__, request_url, method='get', version='v2',
                                                      charid=uid)

                if code == 200:
                    ships[asset_id]['location_name'] = result['name']
                elif code == 403 or code == 401:
                    ships[asset_id]['location_name'] = "CITADEL FORBIDDEN"
                elif code == 404:
                    ships[asset_id]['location_name'] = 'CITADEL NOT FOUND'
                else:
                    ships[asset_id]['location_name'] = "CITADEL ERROR"
            else:
                ships[asset_id]['location_name'] = 'TYPE UNKNOWN'

        if asset_typeid in list(carriers):
            ships[asset_id]['type'] = carriers[asset_typeid]
            ships[asset_id]['class'] = "Carrier"
        elif asset_typeid in list(dreads):
            ships[asset_id]['type'] = dreads[asset_typeid]
            ships[asset_id]['class'] = "Dreadnought"
        elif asset_typeid in list(fax):
            ships[asset_id]['type'] = fax[asset_typeid]
            ships[asset_id]['class'] = "FAX"

    # is this character flying a titan/super?
    # this is last to override the asset search with the active super (if any)

    active_typeid = current_ship.get('ship_type_id')
    active_id = current_ship.get('ship_item_id')

    if active_typeid in list(carriers) + list(dreads) + list(fax):
        # setup basics
        ships[active_id] = basic_pilot
        ships[active_id]['typeid'] = active_typeid
        ships[active_id]['item_id'] = active_id
        ships[active_id]['main_charname'] = main
        ships[active_id]['active'] = True
        ships[active_id]['location_name'] = location['location']
        # more complex location ids and names can be filled in later?

    # actual ship specific shit
    if active_typeid in list(carriers):
        ships[active_id]['type'] = carriers[active_typeid]
        ships[active_id]['class'] = "Carrier"

    elif active_typeid in list(dreads):
        ships[active_id]['type'] = dreads[active_typeid]
        ships[active_id]['class'] = "Dreadnought"

    elif active_typeid in list(fax):
        ships[active_id]['type'] = fax[active_typeid]
        ships[active_id]['class'] = "FAX"

    return ships
