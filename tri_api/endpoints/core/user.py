from flask import request
from tri_api import app

@app.route('/core/user/<int:char_id>/', methods=['GET'])
def core_user(char_id):
    from flask import Response, request
    from json import dumps

    import ldap.modlist
    import common.logger as _logger
    import common.credentials.ldap as _ldap

    try:
        try:
            char_id = int(char_id)
        except ValueError:
            js = dumps({'error': 'char_id is not an integer'})
            return Response(js, status=401, mimetype='application/json')

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
                                       filterstr='(&(objectclass=pilot)(uid={0}))'.format(char_id),
                                       attrlist=['uid', 'altOf', 'characterName', 'corporation', 'corporationName',
                                                     'alliance', 'allianceName', 'authGroup'])
        except ldap.LDAPError as error:
            _logger.log('[' + __name__ + '] unable to fetch ldap users: {}'.format(error), _logger.LogLevel.ERROR)
            raise

        if users.__len__() != 1:
            js = dumps({'error': 'char_id={0} returned no or too many entries'.format(char_id)})
            return Response(js, status=404, mimetype='application/json')

        _, udata = users[0]

        if 'altOf' in udata:
            try:
                users = ldap_conn.search_s('ou=People,dc=triumvirate,dc=rocks', ldap.SCOPE_SUBTREE,
                                           filterstr='(&(objectclass=pilot)(uid={0}))'.format(udata['altOf'][0].decode('utf-8')),
                                           attrlist=['uid', 'altOf', 'characterName', 'corporation', 'corporationName',
                                                     'alliance', 'allianceName', 'authGroup'])

                _logger.log('[' + __name__ + '] user length: {0} [{1}]'.format(users.__len__(), users),
                            _logger.LogLevel.INFO)

                if users.__len__() != 1:
                    js = dumps({'error': 'char_id: {0} is altOf {1} which is not registered'.format(char_id, udata['altOf'])})
                    return Response(js, status=404, mimetype='application/json')

                _, udata = users[0]
            except ldap.LDAPError as error:
                _logger.log('[' + __name__ + '] unable to fetch ldap users: {}'.format(error), _logger.LogLevel.ERROR)
                raise

        main_char_id = int(udata['uid'][0].decode('utf-8'))
        main_char_name = udata['characterName'][0].decode('utf-8')

        main_corp_id = udata['corporation'][0].decode('utf-8')
        main_corp_name = udata['corporationName'][0].decode('utf-8')

        main_ally_id = udata['alliance'][0].decode('utf-8')
        main_ally_name = udata['allianceName'][0].decode('utf-8')

        main_groups = [entry.decode('utf-8') for entry in udata['characterName']]

        js = dumps({
            'character_id': main_char_id,
            'character_name': main_char_name,
            'corporation_id': main_corp_id,
            'corporation_name': main_corp_name,
            'alliance_id': main_ally_id,
            'alliance_name': main_ally_name,
            'groups': main_groups
        })
        return Response(js, status=200, mimetype='application/json')
    except Exception as error:
        js = dumps({'error': str(error)})
        return Response(js, status=500, mimetype='application/json')
