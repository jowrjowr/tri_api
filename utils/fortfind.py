import requests
import common.esihelpers as _esihelpers
import common.ldaphelpers as _ldaphelpers
import common.request_esi

alliance_id = 933731581

corpid = 1


request_url = "alliances/{0}/corporations".format(alliance_id)
code, corps = common.request_esi.esi(__name__, request_url, version='v1')

targets = [ 35833 ]

for corpid in corps:

    if corpid == 98560155:
        continue

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(esiAccessToken=*)(|(corporationRole=Station_Manager)(corporationRole=Director))(esiScope=esi-search.search_structures.v1)(esiScope=esi-universe.read_structures.v1)(corporation={}))'.format(corpid)
    attrlist=['uid', 'corporation', 'corporationName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    charid = None
    corpname = None

    for dn, info in result.items():
        if charid is None:
            charid = info['uid']
            corpname = info['corporationName']

    request_url = "corporations/{0}/structures/".format(corpid)
    code, result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

    for item in result:
        type_id = item['type_id']
        structure_id = item['structure_id']
        system_id = item['system_id']

        if type_id not in targets:
            continue

        #type_info = _esihelpers.type_info(type_id)
        system_info = _esihelpers.solar_system_info(system_id)

        if system_info['region_id'] != 10000009:
            continue

        system_name = system_info['solar_system_name']

        request_url = "universe/structures/{0}/".format(structure_id)
        code, s_result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

        structure_name = s_result['name']

        msg = "{0} - {1}".format(corpname, structure_name)
        print(msg)

    continue

    faction_forts = [ 47512, 47513, 47514, 47515, 47516 ]


    msg = "{0} - {1}".format(type_info['name'], system_info['solar_system_name'])
    print(msg)
