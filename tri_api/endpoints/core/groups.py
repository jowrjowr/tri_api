from flask import request
from tri_api import app

@app.route('/core/group/<group>/<target>', methods=[ 'DELETE', 'POST' ])
def core_group_manage(group, target):

    from flask import request, Response
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger

    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('log_charid')    # logging purposes

    # translate target to a charid

    if target.isdigit():
        # should be close enough
        charid = target
    else:
        # not a digit so assume name. find it.
        result = _ldaphelpers.ldap_name2id(__name__, target)
        if result == None:
            msg = 'unable to locate charname {}'.format(target)
            js = json.dumps({ 'error': msg })
            return Response(js, status=404, mimetype='application/json')
        else:
            charid = result['uid']

    if request.method == 'DELETE':
        _logger.securitylog(__name__, 'removed charid {0} from group {1}'.format(charid, group), ipaddress=ipaddress, charid=log_charid)
        return group_DELETE(group, charid)

    # add the char to a group
    if request.method == 'POST':
        _logger.securitylog(__name__, 'added charid {0} to group {1}'.format(charid, group), ipaddress=ipaddress, charid=log_charid)
        return group_ADD(group, charid)

def group_DELETE(group, charid):

    import json
    import ldap
    import ldap.modlist
    import common.logger as _logger
    import common.credentials.ldap as _ldap
    import common.ldaphelpers as _ldaphelpers
    from flask import Response, request

    # initialize connections

    try:
        ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        msg = 'LDAP connection error: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # find the user. partly to get the dn, partly to validate.

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=['characterName', 'authGroup' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')


    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=404, mimetype='application/json')


    (dn, info), = result.items()

    # modify the user

    group = group.encode('utf-8')
    mod_attrs = [ (ldap.MOD_DELETE, 'authGroup', group) ]

    try:
        ldap_conn.modify_s(dn, mod_attrs)
    except ldap.LDAPError as error:
        msg = 'unable to modify {0}: {1}'.format(dn, error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    return Response({}, status=200, mimetype='application/json')

def group_ADD(group, charid):

    import json
    import ldap
    import ldap.modlist
    import common.logger as _logger
    import common.credentials.ldap as _ldap
    import common.ldaphelpers as _ldaphelpers
    from flask import Response, request

    # initialize connections

    try:
        ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        msg = 'LDAP connection error: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # find the user. partly to get the dn, partly to validate.

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=['characterName', 'authGroup' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')


    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=404, mimetype='application/json')


    (dn, info), = result.items()

    # modify the user

    group = group.encode('utf-8')
    mod_attrs = [ (ldap.MOD_ADD, 'authGroup', group) ]

    try:
        ldap_conn.modify_s(dn, mod_attrs)
    except ldap.LDAPError as error:
        msg = 'unable to modify {0}: {1}'.format(dn, error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    return Response({}, status=200, mimetype='application/json')


@app.route('/core/group/<group>', methods=[ 'GET' ])
def core_group_members(group):

    import json
    import common.logger as _logger
    import common.ldaphelpers as _ldaphelpers
    import common.request_esi
    from flask import Response, request

    # get the list of group members for this group

    ipaddress = request.headers['X-Real-Ip']

    # snag groups

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(authGroup={})'.format(group)
    attrlist=['characterName', 'authGroup', 'uid', 'corporation', 'corporationName', 'alliance', 'allianceName', 'teamspeakdbid', 'esiAccessToken', 'discordAccessToken' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')


    if result == None:
        js = json.dumps({})
        return Response(js, status=200, mimetype='application/json')

    # construct the response object

    response = dict()
    response['count'] = len(result)
    response['users'] = []

    for user in result.keys():

        details = result[user]

        info = dict()
        info['uid'] = int( details['uid'] )
        info['charname'] = details['characterName']
        info['allianceid'] = details.get('alliance')
        info['alliance_name'] = details.get('allianceName')
        info['corpid'] = details.get('corporation')
        info['corp_name'] = details.get('corporationName')

        # ESI token status
        token = details['esiAccessToken']
        if token == None:
            info['esi_token'] = False
        else:
            info['esi_token'] = True

        # discord token status
        token = details['discordAccessToken']
        if token == None:
            info['discord_token'] = False
        else:
            info['discord_token'] = True

        # comms status
        teamspeak = details['teamspeakdbid']
        if teamspeak == None:
            info['teamspeak'] = False
        else:
            info['teamspeak'] = True

        response['users'].append(info)

    js = json.dumps(response)
    return Response(js, status=200, mimetype='application/json')

@app.route('/core/chargroups/<target>', methods=[ 'GET' ])
def core_chargroups(target):

    import json
    import common.logger as _logger
    import common.ldaphelpers as _ldaphelpers
    from flask import Response, request

    # get the list of groups for this charid
    ipaddress = request.args.get('log_ip')
    # translate target to a charid

    if target.isdigit():
        # should be close enough
        charid = target
    else:
        # not a digit so assume name. find it.
        result = _ldaphelpers.ldap_name2id(__name__, target)
        if result == None:
            msg = 'unable to locate charname {}'.format(target)
            js = json.dumps({ 'error': msg })
            return Response(js, status=404, mimetype='application/json')
        else:
            charid = int(result['uid'])

    # snag groups

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=['characterName', 'authGroup' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')


    if result == None:
        msg = 'charid {0} not in ldap'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=404, mimetype='application/json')


    (dn, info), = result.items()

    response = dict()
    response['groups'] = info['authGroup']

    js = json.dumps(response)
    return Response(js, status=200, mimetype='application/json')
