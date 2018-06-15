import sys
from common.check_role import check_role
from concurrent.futures import ThreadPoolExecutor, as_completed
import common.esihelpers as _esihelpers
import common.ldaphelpers as _ldaphelpers
import common.logger as _logger
import common.request_esi

def structure_search(alliance_id, region_id):
    # find every structure from the authed search that characters
    # in alliance_id can see.

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(esiAccessToken=*)(esiScope=esi-search.search_structures.v1)(esiScope=esi-universe.read_structures.v1)(alliance={}))'.format(alliance_id)
    attrlist=['uid','allianceName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return None

    if result == None:
        msg = 'no tokens for alliance {0}'.format(alliance_id)
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

    printed = False

    # iterate through each system and build a view

    for dn, info in result.items():
        charid = info['uid']

        if not printed:
            print(info['allianceName'])
        with ThreadPoolExecutor(50) as executor:
            futures = { executor.submit(system_structure_search, charid, system): system for system in systems }
            for future in as_completed(futures):
                data = future.result()
#                structures = {**structures, **data}
                structures.update(data)

    return structures

def system_structure_search(charid, solar_system_name):
    # find every structure from the authed search that a character can see

    # get the solar system info

    request_url = 'characters/{0}/search/?categories=structure&search={1}'.format(charid, solar_system_name)
    code, result = common.request_esi.esi(__name__, request_url, version='v3', charid=charid)

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
        code, result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

        if not code == 200:
            # something broke severely
            print(code, result)
            structures[structure_id] = structure
            continue

        structure['owner_id'] = result.get('owner_id')
        structure['name'] = result.get('name')
        structure['type_id'] = result.get('type_id')
        structure['solar_system_id'] = result.get('solar_system_id')

        # get corp&alliance of owner

        request_url = 'corporations/{0}/'.format(structure['owner_id'])
        code, result = common.request_esi.esi(__name__, request_url, version='v4')

        if not code == 200:
            # something broke severely
            print(code, result)
            structure['owner_corpname'] = 'Unknown'
            continue
        structure['owner_corpname'] = result.get('name')
        structure['owner_alliance'] = result.get('alliance_id')

        if result.get('alliance_id'):
            request_url = 'alliances/{0}/'.format(result.get('alliance_id'))
            code, result = common.request_esi.esi(__name__, request_url, version='v3')

            if not code == 200:
                # something broke severely
                print(code, result)
                structure['owner_alliancename'] = 'Unknown'
            else:
                structure['owner_alliancename'] = result.get('name')
        else:
            structure['owner_alliancename'] = None

        # map typeid to name

        request_url = 'universe/types/{0}/'.format(structure['type_id'])
        code, result = common.request_esi.esi(__name__, request_url, version='v3')

        if not code == 200:
            # something broke severely
            print(code, result)
            structure['type_name'] = 'Unknown'
        else:
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

        # get owner info

        structures[structure_id] = structure

    # fetch vulnerability information, if the char has access

    allowed_roles = ['Director', 'Station_Manager']
    code = check_role(charid, allowed_roles)
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

if structures:
    for structure_id in structures.keys():
        structure = structures[structure_id]
        output = "{0},{1}\towner: {2}\talliance: {3}".format(structure['type_name'], structure['name'], structure['owner_corpname'], structure['owner_alliancename'])
        print(output)
