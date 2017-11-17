def storetokens(charid, atoken, rtoken, expires=None, token_type='esi'):
    # refresh a characters token store

    import common.logger as _logger
    import common.credentials.ldap as _ldap
    import common.ldaphelpers as _ldaphelpers
    import ldap
    import time

    _logger.log('[' + __name__ + '] updating {0} tokens for user {1}'.format(token_type, charid),_logger.LogLevel.DEBUG)

    # the ldap way
    ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
    try:
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] LDAP connection error: {}'.format(error),_logger.LogLevel.ERROR)
        return(False, 'error')

    # verify existence. ldap does not like modfying nonexistent objects.

    try:
        users = ldap_conn.search_s('ou=People,dc=triumvirate,dc=rocks', ldap.SCOPE_SUBTREE, filterstr='(&(objectclass=pilot)(uid={0}))'.format(charid), attrlist=['authGroup'])
        user_count = users.__len__()
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] unable to fetch ldap user {0}: {1}'.format(charid,error),_logger.LogLevel.ERROR)

    if user_count == 0:
        # why are we modifyin something that doesn't exist?
        # create the stub user
        code, dn =_ldaphelpers.ldap_create_stub(__name__, charid=charid)

        if code == False:
            # couldn't make the stub
            return False
    else:
        # a user was returned
        dn = users[0][0]

    atoken = [ atoken.encode('utf-8') ]
    rtoken = [ rtoken.encode('utf-8') ]

    if expires == None:
        # set expiration to 'now'
        expires = time.time()

    expires = [ str(expires).encode('utf-8') ]
    mod_attrs = []

    if token_type == 'esi':
        mod_attrs.append((ldap.MOD_REPLACE, 'esiAccessToken', atoken ))
        mod_attrs.append((ldap.MOD_REPLACE, 'esiRefreshToken', rtoken ))
        mod_attrs.append((ldap.MOD_REPLACE, 'esiAccessTokenExpires', expires ))

    elif token_type == 'discord':
        mod_attrs.append((ldap.MOD_REPLACE, 'discordAccessToken', atoken ))
        mod_attrs.append((ldap.MOD_REPLACE, 'discordRefreshToken', rtoken ))
        mod_attrs.append((ldap.MOD_REPLACE, 'discordAccessTokenExpires', expires ))

    try:
        result = ldap_conn.modify_s(dn, mod_attrs)
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] unable to update {0} tokens for {1}: {2}'.format(token_type, charid, error),_logger.LogLevel.ERROR)
        return(False, 'error')
    finally:
        ldap_conn.unbind()

    _logger.log('[' + __name__ + '] {0} tokens for user {1} updated (ldap)'.format(token_type, charid),_logger.LogLevel.DEBUG)
    return(True, 'success')
