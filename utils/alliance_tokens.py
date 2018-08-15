def tokens():

    from common.check_role import check_role
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import common.esihelpers as _esihelpers
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger
    import common.request_esi

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(esiAccessToken=*)(alliance=*))'
    attrlist=['allianceName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    for dn, info in result.items():
        alliance = info.get('allianceName')
        if alliance is not None:
            print(alliance)

tokens()
