from flask import request
from tri_api import app

@app.route('/characters/<main_charid>/alts/<alt_charid>/remove/', methods=['GET', 'DELETE'])
def alt_remove(main_charid, alt_charid):
    from flask import Response
    from json import dumps
    import common.logger as _logger
    import common.ldaphelpers as _ldaphelpers

    # verify that the alt exists and that it has the right main

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(uid={0})(altOf={1}))'.format(alt_charid, main_charid)
    attributes = [ 'uid' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        msg = 'unable to connect to ldap: {}'.format(result)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = dumps({'error': msg})
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        msg = 'alt+main combo does not exist'
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        js = dumps({'error': msg})
        return Response(js, status=404, mimetype='application/json')

    # security logging

    ipaddress = request.headers['X-Real-Ip']
    _logger.securitylog(__name__, 'detatching alt', ipaddress=ipaddress, charid=alt_charid, detail='alt of {0}'.format(main_charid))

    code, result = _ldaphelpers.ldap_altupdate(__name__, None, alt_charid)

    if code == True:
        return Response({}, status=200, mimetype='application/json')
    else:
        msg = 'internal error'
        js = dumps({'error' : msg})
        return Response(js, status=500, mimetype='application/json')

@app.route('/characters/<char_id>/', methods=['GET'])
def characters(char_id):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from common.check_scope import check_scope
    from common.request_esi import esi
    from tri_core.common.scopes import scope
    from flask import Response, request
    from json import dumps

    import common.logger as _logger
    import common.ldaphelpers as _ldaphelpers

    # assume that the char id is main

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='uid={0}'.format(char_id)
    attrlist=['uid', 'characterName', 'corporation', 'alliance', 'esiAccessToken', 'authGroup', 'corporationName', 'allianceName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)
    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = dumps({'error': msg})
        return Response(js, status=500, mimetype='application/json')

    if result == None or len(result) == 0:
        # this SHOULD not happen
        msg = 'charname {0} not in ldap'.format(char_id)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        js = dumps({'error': msg})
        return Response(js, status=404, mimetype='application/json')
    else:
        mains = result

    (dn, info), = mains.items()
    json_dict = {'main': {}, 'alts': []}

    json_dict['main'] = fetch_chardetails(info)

    # grab alt details

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='altOf={0}'.format(char_id)
    attrlist=['uid', 'characterName', 'corporation', 'alliance', 'esiAccessToken', 'authGroup', 'corporationName', 'allianceName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = dumps({'error': msg})
        return Response(js, status=500, mimetype='application/json')
    else:
        users = result

    if users == None:
        # no alts
        js = dumps(json_dict)
        return Response(js, status=200, mimetype='application/json')

    with ThreadPoolExecutor(25) as executor:
        futures = { executor.submit(fetch_chardetails, info): info for dn, info in users.items() }
        for future in as_completed(futures):
            data = future.result()
            json_dict['alts'].append(data)

    _logger.log('[' + __name__ + '] fetched characters successfully', _logger.LogLevel.DEBUG)

    js = dumps(json_dict)
    return Response(js, status=200, mimetype='application/json')

def fetch_chardetails(info):
    from common.check_scope import check_scope
    from common.request_esi import esi
    from tri_core.common.scopes import scope
    from json import dumps

    import common.logger as _logger
    import common.ldaphelpers as _ldaphelpers
    new_entry = dict()

    alt_charid = info['uid']
    alt_charname = info['characterName']

    new_entry['character_id'] = alt_charid
    new_entry['character_name'] = alt_charname
    new_entry['corporation_id'] = info['corporation']
    new_entry['corporation_name'] = info['corporationName']
    new_entry['authgroups'] = info['authGroup']

    if 'alliance' in info:
        new_entry['alliance_id'] = info['alliance']
        new_entry['alliance_name'] = info['allianceName']
    else:
        new_entry['alliance_id'] = None
        new_entry['alliance_name'] = None

    # set some defaults

    new_entry['skill_training_id'] = 'Unknown'
    new_entry['skill_training_level'] = 'Unknown'
    new_entry['skill_training'] = 'Unknown'
    new_entry['skill_finish'] = 'Unknown'
    new_entry['location'] = 'Unknown'
    new_entry['esi_token_valid'] = False

    # determine token status. everything past this requires a live token

    token = info.get('esiAccessToken')
    if token == None:
        new_entry['esi_token'] = False
        new_entry['esi_token_valid'] = False
    else:
        new_entry['esi_token'] = True

    if token == None:
        # we're done with this char
        return new_entry
    else:
        # valid token. check scopes.
        code, result = check_scope('acc_management', charid=alt_charid, scopes=scope)
        # the default is already 'false'
        if code == True:
            new_entry['esi_token_valid'] = True

    # we'll let the token scope status fall where it may and try to get other details

    # fetch skill queue
    request_url = 'characters/' + str(alt_charid) + '/skillqueue/?datasource=tranquility'
    code, result = esi(__name__, request_url, 'get', charid=alt_charid, version='v2')
    _logger.log('[' + __name__ + '] /characters output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        _logger.log('[' + __name__ + '] /characters skillqueue API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        skill_training_id = None

    if len(result) == 0:
        skill_training_id = None
        current_skill = None

    if len(result) > 0:
        try:
            current_skill = result[0]
        except Exception as e:
            skill_training_id = None
            current_skill = None

    if not current_skill == None:
        new_entry['skill_training_id'] = current_skill['skill_id']
        new_entry['skill_training_level'] = current_skill['finished_level']
        try:
            new_entry['skill_finish'] = current_skill['finish_date']
        except Exception as e:
            new_entry['skill_finish'] = 'N/A'
        skill_training_id = current_skill['skill_id']

    if not skill_training_id == None:
        # map the skill id to a name
        request_url = 'universe/names/?datasource=tranquility'
        data = '[{}]'.format(skill_training_id)
        code, result = esi(__name__, request_url, data=data, method='post', version='v2')
        _logger.log('[' + __name__ + '] /universe output: {}'.format(result), _logger.LogLevel.DEBUG)

        if not code == 200:
            _logger.log('[' + __name__ + '] /universe API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
            new_entry['skill_training'] = 'Unknown'
        else:
            new_entry['skill_training'] = result[0]['name']

    # fetch alt location
    request_url = 'characters/{0}/location/?datasource=tranquility'.format(alt_charid)
    code, result = esi(__name__, request_url, method='get', charid=alt_charid, version='v1')
    _logger.log('[' + __name__ + '] /characters output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        _logger.log('[' + __name__ + '] /characters location API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        location = None
    else:
        location = result['solar_system_id']

    new_entry['location_id'] = location

    # map the location to a name
    if location == None:
        new_entry['location'] = 'Unknown'
    else:
        request_url = 'universe/systems/{0}/?datasource=tranquility'.format(location)
        code, result = esi(__name__, request_url, 'get')
        if not code == 200:
            _logger.log('[' + __name__ + '] /universe/systems API error ' + str(code) + ': ' + str(data['error']), _logger.LogLevel.INFO)
            new_entry['location'] = 'Unknown'
        else:
            new_entry['location'] = result['name']

    return new_entry


@app.route('/groups', methods=['GET'])
def groups():
    from common.check_scope import check_scope
    from common.request_esi import esi
    from tri_core.common.scopes import scope
    from flask import Response, request
    from json import dumps

    import ldap.modlist
    import common.logger as _logger
    import common.credentials.ldap as _ldap

    try:
        if 'char_id' not in request.args:
            js = dumps({'error': 'no char_id supplied'})
            return Response(js, status=401, mimetype='application/json')

        try:
            char_id = int(request.args['char_id'])
        except ValueError:
            js = dumps({'error': 'char_id is not an integer'})
            return Response(js, status=401, mimetype='application/json')

        # assume that the char id is main
        ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)

        try:
            ldap_conn.simple_bind_s(_ldap.admin_dn,
                                    _ldap.admin_dn_password)
        except ldap.LDAPError as error:
            _logger.log('[' + __name__ + '] LDAP connection error: {}'.format(error),
                        _logger.LogLevel.ERROR)
            raise

        try:
            users = ldap_conn.search_s('ou=People,dc=triumvirate,dc=rocks', ldap.SCOPE_SUBTREE,
                                       filterstr='(&(objectclass=pilot)(uid={0}))'
                                       .format(char_id),
                                       attrlist=['authGroup'])
        except ldap.LDAPError as error:
            _logger.log('[' + __name__ + '] unable to fetch ldap users: {}'.format(error), _logger.LogLevel.ERROR)
            raise

        if users.__len__() != 1:
            js = dumps({'error': 'char_id={0} returned no or too many entries'.format(char_id)})
            return Response(js, status=404, mimetype='application/json')

        _, udata = users[0]

        try:
            js = dumps([g.decode('utf-8') for g in udata['authGroup']])
            return Response(js, status=200, mimetype='application/json')
        except Exception as error:
            raise
    except Exception as error:
        _logger.log('[' + __name__ + '] characters endpoint failed: {}'.format(error), _logger.LogLevel.ERROR)
        js = dumps({'error': str(error)})
        return Response(js, status=500, mimetype='application/json')
