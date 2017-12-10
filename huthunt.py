import sys

def structure_search(alliance_id, region_id):
    # find every structure from the authed search that characters
    # in alliance_id can see.

    from common.check_role import check_role
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import common.esihelpers as _esihelpers
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger
    import common.request_esi

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(esiAccessToken=*)(esiScope=esi-search.search_structures.v1)(esiScope=esi-universe.read_structures.v1)(alliance={}))'.format(alliance_id)
    attrlist=['uid']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    print(result)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return None

    if result == None:
        msg = 'cn {0} not in ldap'.format(cn)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        return None

    structures = dict()
    region_systems = _esihelpers.region_solar_systems(region_id)

    # suss out an array of human readable system names

    systems = []

    for system in region_systems['systems']:
        systems.append(region_systems['systems'][system]['solar_system_name'])

    if region_systems['error'] is True:
        return None

    # iterate through each system and build a view

    for dn, info in result.items():
        charid = info['uid']
        with ThreadPoolExecutor(50) as executor:
            futures = { executor.submit(system_structure_search, charid, system): system for system in systems }
            for future in as_completed(futures):
                data = future.result()
#                structures = {**structures, **data}
                structures.update(data)

    return structures

def system_structure_search(charid, solar_system_name):
    # find every structure from the authed search that a character can see

    from common.check_role import check_role
    import common.esihelpers as _esihelpers
    import common.logger as _logger
    import common.request_esi

    # get the solar system info

    request_url = 'characters/{0}/search/?categories=structure&search={1}'.format(charid, solar_system_name)
    code, result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

    if not code == 200:
        # something broke severely
        print(code, result)
        return {}

    structures = dict()

    # fetch structure details

    if result.get('structure') is None:
        return {}

    for structure_id in result.get('structure'):
        structure = dict()

        # basic structure details

        request_url = 'universe/structures/{0}/'.format(structure_id)
        code, result = common.request_esi.esi(__name__, request_url, version='v1', charid=charid)

        if not code == 200:
            # something broke severely
            print(code, result)
            structures[structure_id] = structure
            continue

        structure['name'] = result.get('name')
        structure['type_id'] = result.get('type_id')
        structure['solar_system_id'] = result.get('solar_system_id')

        # map typeid to name

        request_url = 'universe/types/{0}/'.format(structure['type_id'])
        code, result = common.request_esi.esi(__name__, request_url, version='v3')

        if not code == 200:
            # something broke severely
            print(code, result)
            structure['type_name'] = 'Unknown'
            continue

        structure['type_name'] = result.get('name')

        # fetch system info

        result = _esihelpers.solar_system_info(structure['solar_system_id'])

        if result['error'] is True:
            # oops
            print(code, result)
            structures[structure_id] = structure
            continue

        structure['solar_system_name'] = result.get('solar_system_name')
        structure['constellation_id'] = result.get('constellation_id')
        structure['constellation_name'] = result.get('constellation_name')
        structure['region_id'] = result.get('region_id')
        structure['region_name'] = result.get('region_name')

        structures[structure_id] = structure

    # fetch vulnerability information, if the char has access

    allowed_roles = ['Director', 'Station_Manager']
    code, result = check_role(__name__, charid, allowed_roles)
    if code is False:
        # nope. we're done.
        return structures

    request_url = 'core/{0}/structures'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, 'get', base='triapi')
    if not code == 200:
        # something broke severely
        print('shit broke')
        return structures

    for structure_id in result.keys():
        info = result[structure_id]
        structure_id = int(structure_id)

        # limited focus.
        if structure_id in structures.keys():
            structures[structure_id]['vuln_dates'] = info['vuln_dates']

    return structures

# detorid           10000005
# immensea          10000025
# insmother         10000009
# tenerfis          10000061
# wicked creek      10000006
# etherium reach    10000027

# army              99006401
# fcon              1006830534
# manifesto         99006109
# solar citizens    99001783

structures = structure_search(sys.argv[1], sys.argv[2])
for structure_id in structures.keys():
    structure = structures[structure_id]
    output = "{0},{1}".format(structure['type_name'], structure['name'])
    print(output)
'''
#structures = structure_search(99006109, 10000005)
structures = structure_search(99006109, 10000027)
for structure_id in structures.keys():
    structure = structures[structure_id]
    output = "{0},{1}".format(structure['type_name'], structure['name'])
    print(output)
'''
def huthunt(alliance_id):
    from common.check_role import check_role
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import common.ldaphelpers as _ldaphelpers
    import common.logger as _logger
    import common.request_esi
    import json

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(esiAccessToken=*)(alliance={}))'.format(alliance_id)
    attrlist=['uid', 'characterName', 'corporation' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return None

    if result == None:
        msg = 'cn {0} not in ldap'.format(cn)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        return None


    for dn, info in result.items():

        charid = info['uid']
        corp_id = info['corporation']
        allowed_roles = ['Director', 'Station_Manager']
        code, result = check_role(__name__, charid, allowed_roles)
        if code == True:
            print('ldap dn: {0}, corp id: {1}'.format(dn, corp_id))
            request_url = 'core/{0}/structures'.format(charid)
            code, result = common.request_esi.esi(__name__, request_url, 'get', base='triapi')
            if not code == 200:
                # something broke severely
                print('shit broke')

            for structure_id in result.keys():
                info = result[structure_id]
                s_name = info['name']
                s_type = info['type_name']
                s_vuln = info['vuln_dates']
                print('structure name: {0} ({1})'.format(s_name, s_type))
                print('vulnerability dates:')
                print(s_vuln)


#huthunt(99004425)
#huthunt(1006830534)
