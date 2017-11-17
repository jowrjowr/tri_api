def maint_activity():
    import common.request_esi
    import common.logger as _logger
    import common.credentials.ldap as _ldap
    import common.ldaphelpers as _ldaphelpers
    import ldap
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor, as_completed

    function = __name__

    _logger.log('[' + function + '] zkillboard activity',_logger.LogLevel.INFO)

    # determine killboard activity of players

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(!(accountStatus=banned))(objectClass=pilot))'
    attrlist=['uid', 'altOf', 'accountStatus']
    code, result = _ldaphelpers.ldap_search(function, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + function + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return None

    _logger.log('[' + function + '] {0} non-banned users in ldap'.format(len(result)),_logger.LogLevel.INFO)

    # pare the list down to uids that are blue or are registered alts of blues

    # make a mapping of characters to alts too
    alt_characters = defaultdict(list)
    characters = dict()

    for dn, info in result.items():

        altof = info['altOf']
        status = info['accountStatus']
        charid = int(info['uid'])

        if charid == 0:
            # sovereign special case
            continue

        if status == 'public' and altof == None:
            # not wasting api time with pubbies
            continue
        if status == 'public' and altof == 'None':
            # not wasting api time with pubbies
            continue

        if not altof == None and not altof == 'None':
            # update the mapping
            altof = int(altof)
            alt_characters[altof].append(charid)

        # add it to the list of things we care about
        characters[dn] = charid

    _logger.log('[' + function + '] {0} blue/registered alt users in ldap'.format(len(characters)),_logger.LogLevel.INFO)

    activity = dict()

    with ThreadPoolExecutor(10) as executor:
        futures = { executor.submit(zkill_info, function, characters[dn], dn): dn for dn in characters.keys() }
        for future in as_completed(futures):
            data = future.result()
            activity[charid] = data


def zkill_info(function, charid, dn):

    import common.request_esi
    import common.logger as _logger
    import common.credentials.ldap as _ldap
    import time
    import ldap

    request_url = 'characterID/{0}/'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, 'get', base='zkill')
    if not code == 200:
        _logger.log('[' + function + '] unable to get zkill info for {0}: {1}'.format(charid, result),_logger.LogLevel.WARNING)
        return None

    # no kills
    if len(result) == 0:
        _logger.log('[' + function + '] no kills for {0}'.format(charid),_logger.LogLevel.DEBUG)
        return None

    try:
        killid = result[0]['killID']
        killtime = result[0]['killTime']
    except Exception as e:
        _logger.log('[' + function + '] unable to parse last kill for {0}: {1}'.format(charid, e),_logger.LogLevel.WARNING)
        return False

    _logger.log('[' + function + '] last kill for {0}: {1}'.format(charid, killtime),_logger.LogLevel.DEBUG)

    # convert to epoch time

    killtime = time.strptime(killtime, "%Y-%m-%d %H:%M:%S")
    killtime = time.mktime(killtime)
    killtime = int(killtime)

    # insert into ldap

    mod_attrs = []

    mod_attrs.append((ldap.MOD_REPLACE, 'lastKillTime', [ str(killtime).encode('utf-8') ]))
    mod_attrs.append((ldap.MOD_REPLACE, 'lastKill', [ str(killid).encode('utf-8') ]))

    ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
    try:
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        _logger.log('[' + function + '] LDAP connection error: {}'.format(error),_logger.LogLevel.ERROR)
        return None

    try:
        result = ldap_conn.modify_s(dn, mod_attrs)
    except Exception as e:
        _logger.log('[' + __name__ + '] unable to update existing user {0} in ldap: {1}'.format(charid, e), _logger.LogLevel.ERROR)

    return

