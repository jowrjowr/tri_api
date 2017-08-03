from flask import request
from tri_api import app

@app.route('/core/allianceaudit/<charid>', methods=[ 'GET' ])
def core_allianceaudit(charid):

    from flask import request, Response
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from common.check_role import check_role
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger
    import common.request_esi
    import json

    # do a corp level audit of who has services

    ipaddress = request.headers['X-Real-Ip']
    log_charid = request.args.get('log_charid')

    _logger.securitylog(__name__, 'corp audit information request', ipaddress=ipaddress, charid=log_charid)

    try:
        charid = int(charid)
    except ValueError:
        _logger.log('[' + __name__ + '] charid parameters must be integer: {0}'.format(charid),
                    _logger.LogLevel.WARNING)
        js = json.dumps({'error': 'charid parameter must be integer'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    # check for auth groups

    allowed_roles = ['tsadmin']
    dn = 'ou=People,dc=triumvirate,dc=rocks'

    code, result = _ldaphelpers.ldap_search(__name__, dn, '(uid={})'.format(charid), ['authGroup'])

    if code == 'error':
        error = 'unable to check auth groups roles for {0}: ({1}) {2}'.format(charid, code, result)
        _logger.log('[' + __name__ + ']' + error,_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=404, mimetype='application/json')

    (_, result), = result.items()

    if not "tsadmin" in result['authGroup']:
        error = 'insufficient corporate roles to access this endpoint.'
        _logger.log('[' + __name__ + '] ' + error, _logger.LogLevel.INFO)
        js = json.dumps({'error': error})
        resp = Response(js, status=403, mimetype='application/json')
        return resp

    # get all entires for triumvirate
    code, result = _ldaphelpers.ldap_search(__name__, dn, 'alliance=933731581',
                                            ['uid', 'corporation', 'esiAccessToken', 'altOf'])

    if code == 'error':
        error = 'unable to fetch all tri ldap entries: ({0}) {1}'.format(code, result)
        _logger.log('[' + __name__ + ']' + error,_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    corp_dict = {'corps': {}, 'supers': {}}

    for cn in result:
        entry = result[cn]

        # esi token audit

        corp_id = entry['corporation']

        if corp_id not in corp_dict['corps']:
            request_url = 'corporations/{}/?datasource=tranquility'.format(corp_id)
            esi_code, esi_result = common.request_esi.esi(__name__, request_url, method='get')

            if not esi_code == 200:
                # something broke severely
                _logger.log('[' + __name__ + '] corporation API error {0}: {1}'.format(code, esi_result['error']),
                            _logger.LogLevel.ERROR)
                error = esi_result['error']
                err_result = {'code': code, 'error': error}
                return code, err_result

            corp_dict['corps'][str(corp_id)] = {}
            corp_dict['corps'][str(corp_id)]['name'] = esi_result['corporation_name']
            corp_dict['corps'][str(corp_id)]['members'] = esi_result['member_count']
            corp_dict['corps'][str(corp_id)]['tokens'] = 0
            corp_dict['corps'][str(corp_id)]['registered'] = 0
            corp_dict['corps'][str(corp_id)]['mains'] = 0

        corp_dict['corps'][str(corp_id)]['registered'] += 1

        if 'esiAccessToken' in entry and entry['esiAccessToken'] is not None and not entry['esiAccessToken'] == '':
            corp_dict['corps'][str(corp_id)]['tokens'] += 1

        if entry['altOf'] is None:
            corp_dict['corps'][str(corp_id)]['mains'] += 1
        else:
            corp_dict['corps'][str(corp_id)]['mains'] += 0

        # supercapital audit
        if entry['esiAccessToken'] is not None:
            request_location_url = 'characters/{}/location/?datasource=tranquility'.format(entry['uid'])
            esi_location_code, esi_location_result = common.request_esi.esi(__name__, request_location_url, method='get',
                                                                            charid=entry['uid'])

            request_ship_url = 'characters/{}/ship/?datasource=tranquility'.format(entry['uid'])
            esi_ship_code, esi_ship_result = common.request_esi.esi(__name__, request_ship_url, method='get',
                                                                    charid=entry['uid'])
            if esi_location_code != 200:
                # something broke severely
                _logger.log('[' + __name__ + '] location API error {0}: {1}'.format(code, esi_location_result['error']),
                            _logger.LogLevel.ERROR)
                error = esi_location_result['error']
                err_result = {'code': code, 'error': error}
                return code, err_result

            if esi_ship_code != 200:
                # something broke severely
                _logger.log('[' + __name__ + '] ship API error {0}: {1}'.format(code, esi_ship_result['error']),
                            _logger.LogLevel.ERROR)
                error = esi_ship_result['error']
                err_result = {'code': code, 'error': error}
                return code, err_result

            request_sys_url = 'universe/systems/{}/?datasource=tranquility'.format(esi_location_result['solar_system_id'])
            esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_sys_url, method='get')

            if esi_system_code != 200:
                # something broke severely
                _logger.log('[' + __name__ + '] ship API error {0}: {1}'.format(code, esi_system_result['error']),
                            _logger.LogLevel.ERROR)
                error = esi_system_result['error']
                err_result = {'code': code, 'error': error}
                return code, err_result

            # check ship
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

            if esi_ship_result['ship_type_id'] in titans.keys():
                corp_dict['supers'][entry['uid']] = {}
                corp_dict['supers'][entry['uid']]['ship'] = titans[esi_ship_result['ship_type_id']]
                corp_dict['supers'][entry['uid']]['type'] = "Titan"
                corp_dict['supers'][entry['uid']]['active'] = True
                corp_dict['supers'][entry['uid']]['location'] = esi_system_result['name']
                corp_dict['supers'][entry['uid']]['corporation'] = corp_dict['corps'][str(corp_id)]['name']

            elif esi_ship_result['ship_type_id'] in supers.keys():
                corp_dict['supers'][entry['uid']] = {}
                corp_dict['supers'][entry['uid']]['ship'] = supers[esi_ship_result['ship_type_id']]
                corp_dict['supers'][entry['uid']]['active'] = True
                corp_dict['supers'][entry['uid']]['location'] = esi_system_result['name']
                corp_dict['supers'][entry['uid']]['type'] = "Supercarrier"
                corp_dict['supers'][entry['uid']]['corporation'] = corp_dict['corps'][str(corp_id)]['name']
            else:
                request_assets_url = 'characters/{}/assets/?datasource=tranquility'.format(entry['uid'])
                esi_assets_code, esi_assets_result = common.request_esi.esi(__name__, request_assets_url, method='get',
                                                                            charid=entry['uid'])

                if esi_assets_code == 403:
                    if esi_assets_code != 200:
                        # something broke severely
                        _logger.log('[' + __name__ + '] asset API error {0}: {1}'.format(code, esi_assets_result['error']),
                                    _logger.LogLevel.ERROR)
                        error = esi_assets_result['error']
                        err_result = {'code': code, 'error': error}
                        return code, err_result

                    for asset in esi_assets_result:
                        if esi_ship_result['ship_type_id'] in titans.keys():
                            corp_dict['supers'][entry['uid']] = {}
                            corp_dict['supers'][entry['uid']]['ship'] = titans[esi_ship_result['ship_type_id']]
                            corp_dict['supers'][entry['uid']]['type'] = "Titan"
                            corp_dict['supers'][entry['uid']]['active'] = False
                            corp_dict['supers'][entry['uid']]['location'] = esi_system_result['name']
                            corp_dict['supers'][entry['uid']]['corporation'] = corp_dict['corps'][str(corp_id)]['name']

                        elif esi_ship_result['ship_type_id'] in supers.keys():
                            corp_dict['supers'][entry['uid']] = {}
                            corp_dict['supers'][entry['uid']]['ship'] = supers[esi_ship_result['ship_type_id']]
                            corp_dict['supers'][entry['uid']]['active'] = False
                            corp_dict['supers'][entry['uid']]['location'] = esi_system_result['name']
                            corp_dict['supers'][entry['uid']]['type'] = "Supercarrier"
                            corp_dict['supers'][entry['uid']]['corporation'] = corp_dict['corps'][str(corp_id)]['name']

    js = json.dumps(corp_dict)
    return Response(js, status=200, mimetype='application/json')

        







