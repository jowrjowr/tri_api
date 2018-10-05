from flask import request, Response, json
from tri_api import app
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import common.ldaphelpers as _ldaphelpers
import common.logger as _logger
import common.esihelpers as _esihelpers
import common.request_esi
from tri_core.common.testing import vg_alliances
from collections import defaultdict

@app.route('/core/allianceaudit/<allianceid>/', methods=[ 'GET' ])
def core_audit_alliance(allianceid):

    # logging

    ipaddress = request.args.get('log_ip')
    if ipaddress is None:
        ipaddress = request.headers['X-Real-Ip']

    charid = request.args.get('charid')

    if charid is None:
        error = 'need a charid to authenticate with'
        js = json.dumps({'error': error})
        resp = Response(js, status=405, mimetype='application/json')
        return resp

    _logger.securitylog(__name__, 'alliance audit', ipaddress=ipaddress, charid=charid, detail='alliance {0}'.format(allianceid))

    # ALL is a meta-endpoint for all the vanguard alliances, plus viral

    viral = 99003916
    alliances = [ allianceid ]

    if allianceid == 'ALL':
        alliances = vg_alliances()
        alliances.append(viral)
    # check for auth groups

    allowed_roles = ['tsadmin', 'command']
    dn = 'ou=People,dc=triumvirate,dc=rocks'

    code, result = _ldaphelpers.ldap_search(__name__, dn, '(uid={})'.format(charid), ['authGroup'])

    if code == 'error':
        error = 'unable to check auth groups roles for {0}: ({1}) {2}'.format(charid, code, result)
        _logger.log('[' + __name__ + ']' + error, _logger.LogLevel.ERROR)
        js = json.dumps({'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        js = json.dumps({'error': msg})
        return Response(js, status=404, mimetype='application/json')

    (_, result), = result.items()

    if not "command" in result['authGroup']:
        error = 'insufficient corporate roles to access this endpoint.'
        _logger.log('[' + __name__ + '] ' + error, _logger.LogLevel.INFO)
        js = json.dumps({'error': error})
        resp = Response(js, status=403, mimetype='application/json')
        return resp

    alliancedata = defaultdict(list)

    # process each alliance with an individual process

    with ProcessPoolExecutor(15) as executor:
        futures = { executor.submit(alliance_data, charid, alliance): allianceid for alliance in alliances }
        for future in as_completed(futures):
            data = future.result()
            alliance_id = data['alliance_id']
            alliance_name = data['alliance_name']

            alliancedata[alliance_id] = dict()
            alliancedata[alliance_id]['name'] = alliance_name
            alliancedata[alliance_id]['corp_data'] = data['alliance_corps']

    js = json.dumps(alliancedata)
    resp = Response(js, status=200, mimetype='application/json')

    return resp

def alliance_data(charid, alliance_id):

    returndata = dict()

    # populate alliance data

    alliance_info = _esihelpers.alliance_info(alliance_id)
    if alliance_info is not None:
        alliance_name = alliance_info['name']
    else:
        alliance_name = 'Unknown'

    returndata['alliance_id'] = alliance_id
    returndata['alliance_name'] = alliance_name

    corps = dict()

    # get alliance corporation
    request_url = 'alliances/{}/corporations/'.format(alliance_id)
    esi_corp_code, esi_corp_result = common.request_esi.esi(__name__, request_url, method='get')

    if not esi_corp_code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] corporation API error {0}: {1}'.format(esi_corp_code, esi_corp_result['error']), _logger.LogLevel.ERROR)
        return returndata


    with ThreadPoolExecutor(10) as executor:
        futures = { executor.submit(audit_corp, charid, corp_id): corp_id for corp_id in esi_corp_result }
        for future in as_completed(futures):
            data = future.result()
            corps[data['id']] = data

    returndata['alliance_corps'] = corps

    return returndata

def audit_corp(charid, corp_id):

    dn = 'ou=People,dc=triumvirate,dc=rocks'

    corp_result = {}

    corp_result['id'] = corp_id


    request_url = 'corporations/{}/'.format(corp_id)
    esi_corporation_code, esi_corporation_result = common.request_esi.esi(__name__, request_url, method='get')

    if not esi_corporation_code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] corporation API error {0}: {1}'.format(esi_corporation_code,
                                                                               esi_corporation_result['error']),
                    _logger.LogLevel.ERROR)
        return corp_result

    corp_result['name'] = esi_corporation_result['name']
    corp_result['members'] = esi_corporation_result['member_count']

    code_mains, result_mains = _ldaphelpers.ldap_search(__name__, dn, '(&(corporation={0})(!(altOf=*)))'
                                                        .format(corp_id), ['uid'])

    if code_mains == 'error':
        error = 'unable to count main ldap users {0}: ({1}) {2}'.format(charid, code_mains, result_mains)
        _logger.log('[' + __name__ + ']' + error, _logger.LogLevel.ERROR)
        return corp_result

    code_registered, result_registered = _ldaphelpers.ldap_search(__name__, dn, 'corporation={0}'.format(corp_id),
                                                                  ['uid'])

    if code_registered == 'error':
        error = 'unable to count registered ldap users {0}: ({1}) {2}'\
            .format(charid, code_registered, result_registered)
        _logger.log('[' + __name__ + ']' + error, _logger.LogLevel.ERROR)
        return corp_result

    code_tokens, result_tokens = _ldaphelpers.ldap_search(__name__, dn, '(&(corporation={0})(esiAccessToken=*))'
                                                          .format(corp_id), ['uid'])

    if code_tokens == 'error':
        error = 'unable to count token\'d ldap users {0}: ({1}) {2}'.format(charid, code_tokens, result_tokens)
        _logger.log('[' + __name__ + ']' + error, _logger.LogLevel.ERROR)
        return corp_result

    if result_tokens is None:
        corp_result['tokens'] = 0
    else:
        corp_result['tokens'] = len(result_tokens)

    if result_registered is None:
        corp_result['registered'] = 0
    else:
        corp_result['registered'] = len(result_registered)

    if result_mains is None:
        corp_result['mains'] = 0
    else:
        corp_result['mains'] = len(result_mains)

    return corp_result
