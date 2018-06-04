from flask import request
from tri_api import app

@app.route('/core/corpaudit/<charid>', methods=[ 'GET' ])
def core_corpaudit(charid):

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
        _logger.log('[' + __name__ + '] charid parameters must be integer: {0}'.format(charid), _logger.LogLevel.WARNING)
        js = json.dumps({ 'error': 'charid parameter must be integer'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    corporation_id_list = []
    character_id_list = []

    dn = 'ou=People,dc=triumvirate,dc=rocks'

    code, char_result = _ldaphelpers.ldap_search(__name__, dn, '(&(|(uid={0})(altOf={0}))(esiAccessToken=*))'
                                                 .format(charid), ['uid', 'corporation', 'corporationName', 'characterName'])

    if code == False:
        error = 'failed to fetch characters for {0}: ({1}) {2}'.format(charid, code, char_result)
        _logger.log('[' + __name__ + ']' + error, _logger.LogLevel.ERROR)
        js = json.dumps({'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    for cn in char_result:
        data = char_result[cn]
        allowed_roles = ['Director', 'Personnel_Manager']
        roles = check_role(data['uid'], allowed_roles)

        if not roles:
            msg = "character {0} has insufficient roles for {1}".format(data['characterName'], data['corporationName'])
            _logger.log('[' + __name__ + '] ' + msg, _logger.LogLevel.INFO)
            continue

        _logger.log('[' + __name__ + '] sufficient roles to view corp auditing information', _logger.LogLevel.DEBUG)

        if data['corporation'] not in corporation_id_list:
            request_url = 'corporations/{0}/members/'.format(data['corporation'])
            code, result = common.request_esi.esi(__name__, request_url, method='get', charid=data['uid'], version='v3')

            if not code == 200:
                # something broke severely
                _logger.log('[' + __name__ + '] corporations API error {0}: {1}'.format(code, result), _logger.LogLevel.ERROR)
                error = result
                result = {'code': code, 'error': error}
                return code, result
            character_id_list = result
            corporation_id_list.append(data['corporation'])

    # start constructing which member has what
    users = dict()
    with ThreadPoolExecutor(25) as executor:
        futures = { executor.submit(fetch_chardetails, user): user for user in character_id_list }
        for future in as_completed(futures):
            #charid = futures[future]['character_id']
            data = future.result()

            if data is not None:
                users[data['charname']] = data
    js = json.dumps(users)
    resp = Response(js, status=200, mimetype='application/json')
    return resp

def fetch_chardetails(charid):

    import common.esihelpers as _esihelpers
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger
    import common.request_esi
    import time

    chardetails = dict()


    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=['characterName', 'authGroup', 'teamspeakdbid', 'esiAccessToken', 'altOf', 'corporation', 'lastKill', 'lastKillTime','corporationName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if result is None or not code:
        # no result? simple response.
        chardetails['location'] = 'Unknown'
        chardetails['corporation'] = 'Unknown'
        chardetails['online'] = 'Unknown'
        chardetails['last_online'] = 'Unknown'
        chardetails['token_status'] = False
        chardetails['teamspeak_status'] = False
        chardetails['isalt'] = 'Unknown'
        chardetails['lastKill'] = None
        chardetails['lastKillTime'] = None
        chardetails['altof'] = None

        # fetch affiliations

        affiliations = _esihelpers.esi_affiliations(charid)

        chardetails['corporation'] = affiliations.get('corpname')
        chardetails['charname'] = affiliations.get('charname')

    else:
        try:
            (dn, info), = result.items()
        except ValueError:
            print("error: {}".format(charid))

        chardetails['charname'] = info['characterName']

        # convert last kill time into human readable

        try:
            chardetails['lastKill'] = info['lastKill']
        except Exception as e:
            chardetails['lastKill'] = None

        try:
            killtime = int(info['lastKillTime'])
            killtime = time.strftime("%Y/%m/%d, %H:%M:%S", time.localtime(killtime))
            chardetails['lastKillTime'] = killtime
        except Exception as e:
            chardetails['lastKillTime'] = None

        corp_id = info['corporation']

        if corp_id is None:
            print("error: {} no corp".format(charid))

        chardetails['corporation'] = info['corporationName']

        # does the char have a token?

        try:
            detail = info['esiAccessToken']
            if len(detail) > 0:
                chardetails['token_status'] = True
            else:
                chardetails['token_status'] = False
        except Exception as e:
            chardetails['token_status'] = False

        # teamspeak registration?
        try:
            detail = info['teamspeakdbid']
            if len(detail) > 0:
                chardetails['teamspeak_status'] = True
            else:
                chardetails['teamspeak_status'] = False
        except Exception as e:
            chardetails['teamspeak_status'] = False

        # is this an alt?

        # cast the altof detail to something useful

        try:
            detail = info['altOf']
        except Exception as e:
            detail = None

        # str(None) == False
        if str(detail).isdigit():
            chardetails['isalt'] = True
            request_url = 'characters/{0}/'.format(detail)
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if not code == 200:
                _logger.log('[' + __name__ + '] /characters API error {0}: {1}'.format(code, result), _logger.LogLevel.WARNING)
            try:
                chardetails['altof'] = result['name']
            except KeyError as error:
                _logger.log('[' + __name__ + '] User does not exist: {0})'.format(charid), _logger.LogLevel.ERROR)
                chardetails['altof'] = 'Unknown'
        else:
            chardetails['altof'] = None
            chardetails['isalt'] = False

        ## start fetching character-specific information

        #
        request_url = 'characters/{0}/location/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

        if not code == 200:
            # it doesn't really matter
            _logger.log('[' + __name__ + '] characters loction API error {0}: {1}'.format(code, result),_logger.LogLevel.DEBUG)
            location = None
            chardetails['location_id'] = location
            chardetails['location'] = 'Unknown'
        else:
            # can include either station_id or structure_id
            location = result['solar_system_id']
            chardetails['location_id'] = location

        request_url = 'characters/{0}/location/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

        if not code == 200:
            # it doesn't really matter
            _logger.log('[' + __name__ + '] characters loction API error {0}: {1}'.format(code, result),_logger.LogLevel.DEBUG)
            location = None
        else:
            # can include either station_id or structure_id
            location = result['solar_system_id']

        chardetails['location_id'] = location

        # map the location to a name
        if location == None:
            chardetails['location'] = 'Unknown'
        else:
            request_url = 'universe/systems/{0}/'.format(location)
            code, result = common.request_esi.esi(__name__, request_url, 'get', version='v4')
            if not code == 200:
                _logger.log('[' + __name__ + '] /universe/systems API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.INFO)
                chardetails['location'] = 'Unknown'
            else:
                chardetails['location'] = result['name']

        # get online status

        request_url = 'characters/{0}/online/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v2')

        if not code == 200:
            # it doesn't really matter
            _logger.log('[' + __name__ + '] characters online API error {0}: {1}'.format(code, result['error']),_logger.LogLevel.DEBUG)
            location = None
            chardetails['online'] = 'Unknown'
            chardetails['last_online'] = 'Unknown'
        else:
            chardetails['online'] = result['online']
            chardetails['last_online'] = result['last_login']
        try:
            request_url_corp = 'corporations/{0}/'.format(corp_id)
            code_corp, result_corp = common.request_esi.esi(__name__, request_url_corp, 'get')

            if not code_corp == 200:
                _logger.log('[' + __name__ + '] /corporations API error {0}: {1}'.format(code_corp, result_corp['error']), _logger.LogLevel.WARNING)
            else:
                chardetails['corporation'] = result_corp['name']
        except KeyError as error:
            _logger.log('[' + __name__ + '] corporation id does not exist: {0}'.format(corp_id), _logger.LogLevel.ERROR)
            charname = None
    return chardetails


