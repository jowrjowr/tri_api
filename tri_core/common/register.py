def registeruser(charid, atoken, rtoken, isalt, altof):
    # put the barest skeleton of information into ldap/mysql

    import common.logger as _logger
    import common.credentials.database as _database
    import common.credentials.ldap as _ldap
    import common.request_esi
    from common.graphite import sendmetric
    import ldap
    import json
    import datetime
    import uuid
    import time

    from datetime import datetime
    from passlib.hash import ldap_salted_sha1

    # get character affiliations

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    if isalt == False:
        _logger.log('[' + __name__ + '] registering user {}'.format(charid),_logger.LogLevel.INFO)
    else:
        _logger.log('[' + __name__ + '] registering user {0} (alt of {1})'.format(charid, altof),_logger.LogLevel.INFO)


    ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
    try:
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] LDAP connection error: {}'.format(error),_logger.LogLevel.ERROR)
        return(False, 'error')

    # character info

    request_url = 'characters/{0}/?datasource=tranquility'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v4')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get character info for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return(False, 'error')

    charname = result['name']
    corpid = result.get('corporation_id')

    # alliance id, if any
    request_url = 'corporations/{0}/?datasource=tranquility'.format(corpid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v3')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get character info for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return(False, 'error')

    allianceid = result.get('alliance_id')
    corpname = result.get('corporation_name')

    # setup the service user/pass

    serviceuser = charname
    serviceuser = serviceuser.replace(" ", '')
    serviceuser = serviceuser.replace("'", '')
    servicepass = uuid.uuid4().hex[:8]

    # store in LDAP

    cn = charname.replace(" ", '')
    cn = cn.replace("'", '')
    cn = cn.lower()
    dn = "cn={},ou=People,dc=triumvirate,dc=rocks".format(cn)
    # build a random password until one is built for the user
    password = uuid.uuid4().hex
    password_hash = ldap_salted_sha1.hash(password)

    user = dict()
    user['cn'] = cn
    user['charid'] = charid
    user['charname'] = charname
    user['accountstatus'] = 'blue'
    user['corpid'] = corpid
    user['allianceid'] = allianceid
    user['atoken'] = atoken
    user['rtoken'] = rtoken
    user['password_hash'] = password_hash

    # alt storage
    if isalt == True and not altof == None:
        user['altof'] = altof

    # sort out basic auth groups

    authgroups = ['public', 'vanguard'] # default level of access for blues
    if 'allianceid' in user.keys():
        if user['allianceid'] == 933731581:
            # tri specific authgroup
            authgroups.append('triumvirate')

    user['authgroup'] = authgroups
    # encode to make ldap happy
    for item in user.keys():
        # everything but authgroup is a single valued entry that needs to be encoded
        if not item == 'authgroup':
            if not user[item] == None:
                user[item] = str(user[item]).encode('utf-8')
        else:
            newgroups = []
            for group in authgroups:
                group = str(group).encode('utf-8')
                newgroups.append(group)
            user['authgroup'] = newgroups

    # build the ldap object
    attrs = []
    attrs.append(('objectClass', ['top'.encode('utf-8'), 'pilot'.encode('utf-8'), 'simpleSecurityObject'.encode('utf-8'), 'organizationalPerson'.encode('utf-8')]))
    attrs.append(('sn', [user['cn']]))
    attrs.append(('cn', [user['cn']]))
    attrs.append(('uid', [user['charid']]))
    attrs.append(('characterName', [user['charname']]))
    attrs.append(('accountStatus', [user['accountstatus']]))
    attrs.append(('authGroup', user['authgroup']))
    attrs.append(('corporation', [user['corpid']]))
    if not allianceid == None:
        # ldap does NOT like NoneType :/
        attrs.append(('alliance', [user['allianceid']]))
    attrs.append(('esiAccessToken', [user['atoken']]))
    attrs.append(('esiRefreshToken', [user['rtoken']]))
    attrs.append(('userPassword', [user['password_hash']]))

    if isalt == True:
        try:
            attrs.append(('altOf', [user['altof']]))
        except Exception as e:
            pass
    # build out the modification in case
    mod_attrs = []
    for attr in attrs:
        attribute = (ldap.MOD_REPLACE,) + attr
        mod_attrs.append(attribute)

    # check if it exists
    # ldap doesn't really have a replace into like mysql...

    try:
        # search specifically for users with a defined uid (everyone, tbh) and a defined refresh token (not everyone)
        result = ldap_conn.search_s(
            'ou=People,dc=triumvirate,dc=rocks',
            ldap.SCOPE_SUBTREE,
            filterstr='(uid={})'.format(charid),
        )
        record_count = result.__len__()
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] unable to fetch ldap information for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return(False, 'error')

    if record_count == 0:
        try:
            result = ldap_conn.add_s(dn, attrs)
        except Exception as e:
            _logger.log('[' + __name__ + '] unable to register user {0} in ldap: {1}'.format(charid, e), _logger.LogLevel.ERROR)
            return(False, 'error')
    else:
        try:
            result = ldap_conn.modify_s(dn, mod_attrs)
        except Exception as e:
            _logger.log('[' + __name__ + '] unable to update existing user {0} in ldap: {1}'.format(charid, e), _logger.LogLevel.ERROR)
            return(False, 'error')

    if isalt == True:
        _logger.log('[' + __name__ + '] new user {0} ({1}) (alt of {2}) registered (ldap)'.format(charid, charname, altof), _logger.LogLevel.INFO)
    else:
        _logger.log('[' + __name__ + '] new user {0} ({1}) registered (ldap)'.format(charid, charname), _logger.LogLevel.INFO)

    return(True, 'success')

