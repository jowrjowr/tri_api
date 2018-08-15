from common.request_esi import esi
import common.request_esi
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import math
from concurrent.futures import ThreadPoolExecutor, as_completed


def hunt():

    alliance_id=933731581

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(&(esiAccessToken=*)(esiScope=esi-location.read_ship_type.v1)(alliance={}))'.format(alliance_id)
    attrlist=['uid', 'characterName']

    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    characters = []

    bubble_range = 0
    at_sun = []
    total = 0

    for dn, info in result.items():
        charid = info['uid']
        characters.append(charid)


    with ThreadPoolExecutor(50) as executor:
        futures = { executor.submit(location, charid): charid for charid in characters}
        for future in as_completed(futures):
            data = future.result()

            if data is False or data is None:
                continue

            total += 1

            charid, r, x, y, z, super, typeinfo = data
            charinfo = _esihelpers.character_info(charid)
            charname = charinfo['name']
            corpid = charinfo['corporation_id']
            corpinfo = _esihelpers.corporation_info(corpid)
            corpname = corpinfo['name']
            shipname = typeinfo['name']


#            r = r / 1.50e11

            if r < 150000:
                bubble_range += 1

            if (x, y, z) == (0.0, 0.0, 0.0):
                at_sun.append((charid,charname))

#            if r > 150000 and (x, y, z) != (0.0, 0.0, 0.0):
            if 1 == 1:
                output = "{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}".format(super, r, charname, corpname, shipname,  x, y, z)
                print(output)



    print(bubble_range)
    print(len(at_sun))
    print(total)

def scalar_distance(x1, y1, z1, x2=0, y2=0, z2=0):

    # scalar distance between two points

    x = x1 - x2
    y = y1 - y2
    z = z1 - z2

    return math.sqrt(x**2 + y**2 + z**2)

def location(charid):

    # reference point
    # https://zkillboard.com/kill/71335986/

    x2, y2, z2 = (1011610190519.034, -43434354634.67464, -224486810735.37875)

#    x2, y2, z2 = (0, 0, 0)

    # capital types from lucia

    capitals = [ 42124,42243,45647,42242,45645,42126,42241,45649,11567,3764,671,23773,
    42125,3514,3628,23919,23917,23913,22852,19720,19726,19724,19722,28352,37604,37606,
    37605,37607,23757,23911,23915,24483 ]

    supers = [ 42126,42241,45649,11567,3764,671,23773, 42125,3514,3628,23919,23917,23913,22852]


    # where is the character

    request_url = 'characters/{0}/location/'.format(charid)
    code, result = esi(__name__, request_url, version='v1', method='get', charid=charid)

    if code != 200:
        print('cant get location info for charid {0}: {1}'.format(charid, result))
        return None

    solar_system_id = result.get('solar_system_id')

    if solar_system_id != 30004807:
        #pass
        return False

    request_url = 'characters/{0}/ship/'.format(charid)
    code, result = esi(__name__, request_url, version='v1', method='get', charid=charid)

    if code != 200:
        print('cant get ship info for charid {0}: {1}'.format(charid, result))
        return None
    ship_asset_id = result.get('ship_item_id')

    ship_type = result.get('ship_type_id')
    if ship_type not in capitals:
        return False

    if ship_type in supers:
        super = True
    else:
        super = False

    request_url = 'characters/{0}/assets/locations/'.format(charid)
    request_data = '[{}]'.format(ship_asset_id)

    code, result = esi(__name__, request_url, method='post', version='v2', charid=charid, data=request_data)

    position = result[0]['position']

    x, y, z = position['x'], position['y'], position['z']

    r = scalar_distance(x,y,z, x2, y2, z2)

    typeinfo = _esihelpers.type_info(ship_type)
    return (charid, r, x, y, z, super, typeinfo)

hunt()
#print(location(93182066))
#location(90622096)
#location(92738971)


