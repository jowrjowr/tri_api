from tri_api import app
from flask import request, json, Response
from tri_core.common.session import readsession
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.request_esi

@app.route('/core/blacklist/confirmed', methods=[ 'GET' ])
def core_blacklist():

    import re
    import time

    # get all users that are confirmed blacklisted

    ipaddress = request.headers['X-Real-Ip']
    cookie = request.cookies.get('tri_core')

    if cookie is not None:
        payload = readsession(cookie)
    else:
        payload = None

    if payload is not None:
        log_charid = payload['charID']
    else:
        log_charid = None

    _logger.securitylog(__name__, 'viewed blacklist', detail='confirmed', ipaddress=ipaddress, charid=log_charid)

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='accountStatus=banned'
    attrlist=['characterName', 'uid', 'altOf', 'banApprovedBy', 'banApprovedOn', 'banReason', 'banReportedBy', 'banDescription' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # start converting the bans into friendly information

    banlist = dict()

    for dn, info in result.items():
        charname = info['characterName']
        banlist[charname] = info
        # map the times to friendlier info

        fuckyou = int(float(info['banApprovedOn']))
        banlist[charname]['banApprovedOn'] = time.strftime('%Y-%m-%d', time.localtime(fuckyou))

        # how the fuck did ban reasons/descriptions get stored this way?!

        convert = [ 'banDescription', 'banReason' ]
        for thing in convert:

            if banlist[charname][thing] == '': continue
            if banlist[charname][thing] == None: continue
            banlist[charname][thing] = re.sub('"$', '', banlist[charname][thing])
            banlist[charname][thing] = re.sub("'$", '', banlist[charname][thing])
            banlist[charname][thing] = re.sub("^b'", '', banlist[charname][thing])
            banlist[charname][thing] = re.sub('^b"', '', banlist[charname][thing])
            banlist[charname][thing] = re.sub('\\\\r', '<br>', banlist[charname][thing])
            banlist[charname][thing] = re.sub('\\\\n', '<br>', banlist[charname][thing])

        # map the main of the banned alt to a name

        if info['altOf'] is not None:

            main_charid = info['altOf']

            banlist[charname]['isalt'] = True
            banlist[charname]['main_charid'] = main_charid

            main_name = _ldaphelpers.ldap_uid2name(__name__, main_charid)

            if main_name is False or None:

                request_url = 'characters/{0}/'.format(main_charid)
                code, result = common.request_esi.esi(__name__, request_url, 'get')

                if not code == 200:
                    _logger.log('[' + function + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.WARNING)
                    banlist[charname]['main_charname'] = 'Unknown'
                try:
                    banlist[charname]['main_charname'] = result['name']
                except KeyError as error:
                    _logger.log('[' + function + '] User does not exist: {0})'.format(charid), _logger.LogLevel.ERROR)
                    banlist[charname]['main_charname'] = 'Unknown'
            else:
                banlist[charname]['main_charname'] = main_name
        else:
            banlist[charname]['isalt'] = False

        # map the reporter and approver's ids to names

        approver = _ldaphelpers.ldap_uid2name(__name__, info['banApprovedBy'])
        reporter = _ldaphelpers.ldap_uid2name(__name__, info['banReportedBy'])

        if approver is False or None:
            # no loger in ldap?
            request_url = 'characters/{0}/'.format(info['banApprovedBy'])
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if not code == 200:
                _logger.log('[' + function + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.WARNING)
                banlist[charname]['banApprovedBy'] = 'Unknown'
            try:
                banlist[charname]['banApprovedBy'] = result['name']
            except KeyError as error:
                _logger.log('[' + function + '] User does not exist: {0})'.format(charid), _logger.LogLevel.ERROR)
                banlist[charname]['banApprovedBy'] = 'Unknown'
        else:
            banlist[charname]['banApprovedBy'] = approver

        if reporter is False or None:
            request_url = 'characters/{0}/'.format(info['banReportedBy'])
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if not code == 200:
                _logger.log('[' + function + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.WARNING)
                banlist[charname]['banReportedBy'] = 'Unknown'
            try:
                banlist[charname]['banReportedBy'] = result['name']
            except KeyError as error:
                _logger.log('[' + function + '] User does not exist: {0})'.format(charid), _logger.LogLevel.ERROR)
                banlist[charname]['banReportedBy'] = 'Unknown'
        else:
            banlist[charname]['banReportedBy'] = reporter

    return Response(json.dumps(banlist), status=200, mimetype='application/json')

@app.route('/core/blacklist/pending', methods=[ 'GET' ])
def core_blacklist_pending():

    import re
    import time

    # get all users that are waiting to be blacklisted

    ipaddress = request.headers['X-Real-Ip']
    cookie = request.cookies.get('tri_core')

    if cookie is not None:
        payload = readsession(cookie)
    else:
        payload = None

    if payload is not None:
        log_charid = payload['charID']
    else:
        log_charid = None
    _logger.securitylog(__name__, 'viewed blacklist', detail='pending', ipaddress=ipaddress, charid=log_charid)

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='authGroup=ban_pending'
    attrlist=['characterName', 'uid', 'altOf', 'banReason', 'banReportedBy', 'banDescription' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # start converting the bans into friendly information

    banlist = dict()

    for dn, info in result.items():
        charname = info['characterName']
        banlist[charname] = info
        # map the times to friendlier info

        # how the fuck did ban reasons/descriptions get stored this way?!

        convert = [ 'banDescription', 'banReason' ]
        for thing in convert:

            if banlist[charname][thing] == '': continue
            if banlist[charname][thing] == None: continue
            banlist[charname][thing] = re.sub('"$', '', banlist[charname][thing])
            banlist[charname][thing] = re.sub("'$", '', banlist[charname][thing])
            banlist[charname][thing] = re.sub("^b'", '', banlist[charname][thing])
            banlist[charname][thing] = re.sub('^b"', '', banlist[charname][thing])
            banlist[charname][thing] = re.sub('\\\\r', '<br>', banlist[charname][thing])
            banlist[charname][thing] = re.sub('\\\\n', '<br>', banlist[charname][thing])

        # map the main of the banned alt to a name

        if info['altOf'] is not None:

            main_charid = info['altOf']

            banlist[charname]['isalt'] = True
            banlist[charname]['main_charid'] = main_charid

            main_name = _ldaphelpers.ldap_uid2name(__name__, main_charid)

            if main_name is False or None:

                request_url = 'characters/{0}/'.format(main_charid)
                code, result = common.request_esi.esi(__name__, request_url, 'get')

                if not code == 200:
                    _logger.log('[' + function + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.WARNING)
                    banlist[charname]['main_charname'] = 'Unknown'
                try:
                    banlist[charname]['main_charname'] = result['name']
                except KeyError as error:
                    _logger.log('[' + function + '] User does not exist: {0})'.format(charid), _logger.LogLevel.ERROR)
                    banlist[charname]['main_charname'] = 'Unknown'
            else:
                banlist[charname]['main_charname'] = main_name
        else:
            banlist[charname]['isalt'] = False

        # map the reporter and approver's ids to names

        reporter = _ldaphelpers.ldap_uid2name(__name__, info['banReportedBy'])

        if reporter is False or None:
            request_url = 'characters/{0}/'.format(info['banReportedBy'])
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if not code == 200:
                _logger.log('[' + function + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.WARNING)
                banlist[charname]['banReportedBy'] = 'Unknown'
            try:
                banlist[charname]['banReportedBy'] = result['name']
            except KeyError as error:
                _logger.log('[' + function + '] User does not exist: {0})'.format(charid), _logger.LogLevel.ERROR)
                banlist[charname]['banReportedBy'] = 'Unknown'
        else:
            banlist[charname]['banReportedBy'] = reporter

    return Response(json.dumps(banlist), status=200, mimetype='application/json')

@app.route('/core/blacklist/<charid>', methods=[ 'GET' ])
def core_blacklist_details():

    ipaddress = request.headers['X-Real-Ip']

    # maybe not worth bothering?
    return Response({}, status=200, mimetype='application/json')

@app.route('/core/blacklist/<ban_charid>/confirm', methods=[ 'GET' ])
def core_blacklist_confirm(ban_charid):

    import time
    import uuid
    import ldap
    from passlib.hash import ldap_salted_sha1

    # promote someone from 'ban pending' to 'banned'

    # logging
    ipaddress = request.headers['X-Real-Ip']
    log_charid = request.args.get('charid')

    # optional charid override for command line tinkering to record correctly

    _logger.securitylog(__name__, 'blacklist confirm'.format(ban_charid), ipaddress=ipaddress, charid=log_charid, detail='charid {0}'.format(ban_charid))

    # fetch details including main + alts

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(authGroup=ban_pending)(uid={}))'.format(ban_charid)
    attrlist=['characterName', 'uid', 'altOf', 'banReason', 'banDate', 'banReportedBy', 'banDescription' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        msg = 'charid {0} isnt on the pending blacklist'.format(ban_charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    (dn, info), = result.items()

    # setup the ldap connection for the modifications

    ldap_conn = _ldaphelpers.ldap_binding(__name__)

    if ldap_conn == None:
        msg = 'unable to create an ldap connection'
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # this will be true for everyone

    approved_on = str( time.time() ).encode('utf-8')
    approved_by = str( log_charid ).encode('utf-8')
    status = 'banned'.encode('utf-8')
    group = 'banned'.encode('utf-8')

    # scramble password w/ random password
    password = uuid.uuid4().hex
    password_hash = ldap_salted_sha1.hash(password)
    password_hash = password_hash.encode('utf-8')

    mod_attrs = []

    # change account status and authgroup to banned
    # add an approved by/time

    mod_attrs.append((ldap.MOD_REPLACE, 'authGroup', [ group ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'accountStatus', [ status ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'userPassword', [ password_hash ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'banApprovedBy', [ approved_by ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'banApprovedOn', [ approved_on ] ))

    # only because other chars that get sucked up in this might not have these details
    # so synchronize

    mod_attrs.append((ldap.MOD_REPLACE, 'banDate', [ str(info['banDate']).encode('utf-8') ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'banReason', [ str(info['banReason']).encode('utf-8') ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'banReportedBy', [ str(info['banReportedBy']).encode('utf-8') ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'banDescription', [ str(info['banDescription']).encode('utf-8') ] ))

    promote = set()

    altof = info['altOf']

    # this character gets promoted regardless

    promote.add(dn)

    if altof is not None:
        # promote it and all alts to banned
        result = promote(__name__, ldap_conn, altof, 'BANNED', mod_attrs)
        if result == None:
            msg = 'charid {0} does not exist'.format(altof)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg })
            return Response(js, status=500, mimetype='application/json')
        if result == False:
            msg = 'unable to promote {0} to banned'.format(altof)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg })
            return Response(js, status=500, mimetype='application/json')
    # all done
    ldap_conn.unbind()
    return Response({}, status=200, mimetype='application/json')


@app.route('/core/blacklist/<ban_charid>/remove', methods=[ 'GET' ])
def core_blacklist_remove(ban_charid):

    import ldap

    # demote someone from the blacklist

    # logging
    ipaddress = request.headers['X-Real-Ip']
    log_charid = request.args.get('charid')

    # optional charid override for command line tinkering to record correctly

    _logger.securitylog(__name__, 'blacklist remove', ipaddress=ipaddress, charid=log_charid, detail='charid {0}'.format(ban_charid))

    # fetch details

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(authGroup=banned)(uid={}))'.format(ban_charid)
    attrlist=['characterName', 'uid', 'altOf' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        msg = 'charid {0} isnt banned dum-dum'.format(ban_charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    (dn, info), = result.items()

    # setup the ldap connection for the modifications

    ldap_conn = _ldaphelpers.ldap_binding(__name__)

    if ldap_conn == None:
        msg = 'unable to create an ldap connection'
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    mod_attrs = []

    # promoted to pubbie. a step up.

    status = 'public'.encode('utf-8')
    group = status

    mod_attrs.append((ldap.MOD_REPLACE, 'authGroup', [ group ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'accountStatus', [ status ] ))

    purge = [ 'banApprovedBy', 'banApprovedOn', 'banDate', 'banReason', 'banReportedBy' ]

    for attr in purge:
        mod_attrs.append((ldap.MOD_DELETE, attr, None ))

    promote = set()
    promote.add(dn)

    if altof is not None:
        result = promote(__name__, ldap_conn, altof, 'UNBANNED', mod_attrs)
        if result == None:
            msg = 'charid {0} does not exist'.format(altof)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg })
            return Response(js, status=500, mimetype='application/json')
        if result == False:
            msg = 'unable to promote {0} to unbanned'.format(altof)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg })
            return Response(js, status=500, mimetype='application/json')

    # all done
    ldap_conn.unbind()
    return Response({}, status=200, mimetype='application/json')

@app.route('/core/blacklist/<ban_charid>/add', methods=[ 'POST' ])
def core_blacklist_add(ban_charid):

    import ldap

    # put someone into the blacklist, pending confirmation

    ban_data = json.loads(request.data)

    # logging
    ipaddress = request.headers['X-Real-Ip']
    log_charid = request.args.get('charid')

    # optional charid override for command line tinkering to record correctly

    _logger.securitylog(__name__, 'blacklist add', ipaddress=ipaddress, charid=log_charid, detail='charid {0}'.format(ban_charid))

    # fetch details

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='uid={}'.format(ban_charid)
    attrlist=['characterName', 'uid', 'altOf' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        # we'll have to create a stub ldap to hold the ban if there is no ldap entry already
        pass
    (dn, info), = result.items()

    # setup the ldap connection for the modifications

    ldap_conn = _ldaphelpers.ldap_binding(__name__)

    if ldap_conn == None:
        msg = 'unable to create an ldap connection'
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    mod_attrs = []

    # promoted to pubbie. a step up.

    status = 'public'.encode('utf-8')
    group = status

    mod_attrs.append((ldap.MOD_REPLACE, 'authGroup', [ group ] ))
    mod_attrs.append((ldap.MOD_REPLACE, 'accountStatus', [ status ] ))

    purge = [ 'banApprovedBy', 'banApprovedOn', 'banDate', 'banReason', 'banReportedBy' ]

    for attr in purge:
        mod_attrs.append((ldap.MOD_DELETE, attr, None ))

    promote = set()
    promote.add(dn)

    if altof is not None:
        result = promote(__name__, ldap_conn, altof, 'UNBANNED', mod_attrs)
        if result == None:
            msg = 'charid {0} does not exist'.format(altof)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg })
            return Response(js, status=500, mimetype='application/json')
        if result == False:
            msg = 'unable to promote {0} to unbanned'.format(altof)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg })
            return Response(js, status=500, mimetype='application/json')

    # all done
    ldap_conn.unbind()
    return Response({}, status=200, mimetype='application/json')


def promote(function, ldap_conn, charid, reason, modlist):

    # PROMOTIONS!
    # same function is used over and over...

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='uid={}'.format(charid)
    attrlist=['characterName', 'uid' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        ldap_conn.unbind()
        return False

    if result == None:
        # weird.
        return None

    (dn, info), = result.items()

    # the main gets a promotion

    promote = set()
    main_charid = info['uid']
    promote.add(dn)

    # any alts?

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='altOf={}'.format(main_charid)
    attrlist=[ 'characterName', 'uid' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        ldap_conn.unbind()
        return False, msg

    if result is not None:
        for dn, info in result.items():
            # each alt gets a promotion too!
            promote.add(dn)

    for dn in list(promote):
        msg = 'promoting {0} to {1}'.format(dn, reason)

        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)

        try:
            result = ldap_conn.modify_s(dn, modlist)
        except ldap.LDAPError as error:
            msg = 'unable to update ldap information: {}'.format(error)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            ldap_conn.unbind()
            return False
    # all done promoting

    return True

# ban reasons
# 1: "shitlord"
# 2: "spy"
# 3: "rejected applicant"
# 4: "other"

