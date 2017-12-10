def audit_supers():
    import common.request_esi
    import ldap
    import ldap.modlist
    import common.logger as _logger
    import common.credentials.ldap as _ldap

    _logger.log('[' + __name__ + '] auditing supers', _logger.LogLevel.INFO)

    ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)

    try:
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] LDAP connection error: {}'.format(error), _logger.LogLevel.ERROR)

    # fetch all the users

    try:
        users = ldap_conn.search_s('ou=People,dc=triumvirate,dc=rocks', ldap.SCOPE_SUBTREE,
                                   filterstr='(&(objectclass=pilot)(authGroup=trisupers))',
                                   attrlist=['characterName', 'uid', 'corporation', 'alliance', 'esiAccessToken', 'authGroup'])
        user_count = users.__len__()
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] unable to fetch ldap users: {}'.format(error), _logger.LogLevel.ERROR)
        return

    print("Auditing {0} pilots\n----------".format(user_count))

    problems = []

    for user in users:
        dn, X = user

        character_name = X['characterName'][0].decode('utf-8')
        character_id = int(X['uid'][0].decode('utf-8'))
        corporation_id = int(X['corporation'][0].decode('utf-8'))
        alliance_id = int(X['alliance'][0].decode('utf-8'))
        token = X['esiAccessToken'][0].decode('utf-8')
        groups = [item.decode('utf-8') for item in X['authGroup']]

        print("Auditing \"{0}\"...".format(character_name))

        # get character affiliations
        request_url = 'characters/affiliation/'
        data = '[{}]'.format(character_id)
        code, result = common.request_esi.esi(__name__, request_url, method='post', data=data)

        if not code == 200:
            # something broke severely
            _logger.log('[' + __name__ + '] affiliations API error {0}: {1}'.format(code, result['error']),
                        _logger.LogLevel.ERROR)
            error = result['error']
            result = {'code': code, 'error': error}
            return code, result

        corpid = result[0]['corporation_id']
        try:
            allianceid = result[0]['alliance_id']
        except KeyError:
            allianceid = 0

        if corpid != corporation_id:
            print("WARNING: ingame corporation ({0}) does not match ldap data ({1})"
                  .format(corpid, corporation_id))

            if character_name not in problems:
                problems.append(character_name)

        if allianceid != alliance_id:
            print("WARNING: ingame alliance ({0}) does not match ldap data ({1})"
                  .format(allianceid, alliance_id))

            if character_name not in problems:
                problems.append(character_name)

        # get corp & alliance names
        request_url = 'corporations/{0}/'.format(corpid)
        code, result = common.request_esi.esi(__name__, request_url, 'get')

        if code != 200:
            # something broke severely
            _logger.log('[' + __name__ + '] corporations API error {0}: {1}'.format(code, result['error']),
                        _logger.LogLevel.ERROR)
            error = result['error']
            result = {'code': code, 'error': error}
            return code, result

        corp_name = result['corporation_name']

        if allianceid != 0:
            request_url = 'alliances/{0}/'.format(allianceid)
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if code != 200:
                # something broke severely
                _logger.log('[' + __name__ + '] alliances API error {0}: {1}'.format(code, result['error']),
                            _logger.LogLevel.ERROR)
                error = result['error']
                result = {'code': code, 'error': error}
                return code, result

            alliance_name = result['alliance_name']

            print("belongs to {0} in {1}".format(corp_name, alliance_name))

            if(alliance_name != "Triumvirate."):
                print("WARNING: pilot is not in tri")

                if character_name not in problems:
                    problems.append(character_name)

        else:
            print("belongs to {0}".format(corp_name))
            print("WARNING: pilot is not in tri (or any alliance)")

        if character_name not in problems:
            problems.append(character_name)

        # test token
        request_url = 'characters/{0}/wallets/&token={1}'\
            .format(corpid, token)
        code, result = common.request_esi.esi(__name__, request_url, 'get')

        if code != 200:
            if code == 403:
                # token failed
                print("WARNING: ESI Token is invalid")
            else:
                # something broke severely
                _logger.log('[' + __name__ + '] character wallet API error {0}: {1}'.format(code, result['error']),
                            _logger.LogLevel.ERROR)
                error = result['error']
                result = {'code': code, 'error': error}
                return code, result
        else:
            print("INFO: ESI Token is valid")

            if character_name not in problems:
                problems.append(character_name)

        print("---------")

    print("Total {0} problem characters found.".format(len(problems)))

    for char in problems:
        print(char)






