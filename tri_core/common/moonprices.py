import json
import common.request_esi
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import math
import resource
import MySQLdb as mysql
import base64
import common.credentials.database as _database

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

def moon_typedata():
    # fetch all the distinct item types out of the moon database
    msg = 'fetching moon ore type data & prices'
    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)

    # goo bearing ores including jackpots

    ubiquitous = list(range(45490, 45494)) + list(range(46280, 46287))
    common_ore = list(range(45494, 45498)) + list(range(46288, 46296))
    uncommon = list(range(45498, 45502)) + list(range(46296, 46303))
    rare = list(range(45502, 45507)) + list(range(46304, 46312))
    exceptional = list(range(45510, 45514)) + list(range(46312, 46320))

    # standard +15% ore varieties

    standard = list(range(46675, 46690))

    ore_list = standard + ubiquitous + common_ore + uncommon + rare + exceptional
    ore_list.append(46287)
    ore_list.append(46303)

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        return False

    # load the relevant chunks of the SDE

    cursor = sql_conn.cursor()

    query = 'SELECT typeID, materialTypeID, quantity FROM sde.invTypeMaterials'

    invtypematerials = dict()

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        return False
    finally:
        cursor.close()
        sql_conn.close()

    for typeid, mat_typeid, quantity in rows:

        try:
            test = invtypematerials[typeid]
        except KeyError:
            invtypematerials[typeid] = dict()
        finally:
            invtypematerials[typeid][mat_typeid] = quantity

    # now map the ore type to a distinct typeid, and figure out refining

    moon_ores = dict()
    refine_types = set()
    refine_amount = 10000
    refine_yield = 0.85

    for typeid in ore_list:

        moon_ores[typeid] = dict()

        # fetch ore volume from ESI

        request_url = 'universe/types/{0}/'.format(typeid)
        code, result = common.request_esi.esi(__name__, request_url, version='v3')

        if not code == 200:
            msg = 'universe/types/{0}/ error: {1}'.format(typeid, result)
            _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.WARNING)
            continue

        moon_ores[typeid]['name'] = result.get('name')
        moon_ores[typeid]['volume'] = result.get('volume')

        portion_size = result.get('portion_size')
        moon_ores[typeid]['portion_size'] = portion_size

        # now fetch refined composition from the SDE
        # going to assume a specific yield and refine amount for this

        composition = dict()

        for item in invtypematerials.keys():
            if item == typeid:

                mat_list = invtypematerials[item]

                for material in mat_list.keys():
                    quantity = mat_list[material] * refine_amount * refine_yield / portion_size
                    material_typeid = material

                    refine_types.add(material_typeid)
                    composition[material_typeid] = math.floor(quantity)

        moon_ores[typeid]['composition'] = composition

    # intermission - need to sort out pricing for all the typeids the refining spits out

    refine_prices = dict()

    for item in list(refine_types):

        request_url = 'item_prices2.json?char_name=saeka&type_ids={0}&station_ids=60003760&buysell=s'.format(item)
        code, result = common.request_esi.esi(__name__, request_url, base='eve_market')

        if not code == 200:
            msg = 'unable to fetch price for ore {0}: {1}'.format(item, result)
            _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.CRITICAL)
            continue

        try:
            price = result['emd']['result'][0]['row']['price']
        except Exception as e:
            msg = 'unable to fetch price for ore {0}: {1}'.format(item, result)
            _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.CRITICAL)
            continue

        refine_prices[item] = price

    # tie pricing together and make a density calculation

    for ore_type in moon_ores.keys():

        ore = moon_ores[ore_type]
        composition = ore['composition']
        volume = ore['volume']

        ore_price = 0

        for refine_type in composition.keys():

            # divide by refine amount to get the ore per-unit price

            ore_price += ( refine_prices[refine_type] * composition[refine_type] ) / refine_amount

        moon_ores[ore_type]['unit_value'] = ore_price
        moon_ores[ore_type]['density'] = ore_price / volume


    # re-shuffle the dict to a version that's keyed to names

    moon_ores_bytype = moon_ores
    moon_ores_byname = dict()

    for ore in moon_ores.keys():
        ore_name = moon_ores[ore]['name']
        moon_ores_byname[ore_name] = moon_ores[ore]
        moon_ores_byname[ore_name]['typeID'] = ore

    return (moon_ores_byname, moon_ores_bytype)

def moon_scandata():

    # analyze the moon data

    moon_ores_byname, moon_ores_bytype = moon_typedata()

    msg = 'fetching moon scan data'
    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        return False

    # fetch all the scan data

    cursor = sql_conn.cursor()
    query = 'SELECT moonId, oreComposition FROM MoonScans'

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        return False
    finally:
        cursor.close()
        sql_conn.close()

    # calculate moon values

    moons = dict()

    with ThreadPoolExecutor(50) as executor:

        futures = { executor.submit(moon_information, moon, composition, moon_ores_byname): moon for moon, composition in rows }
        for future in as_completed(futures):
            data = future.result()

def moon_information(moon, composition, ore_data):

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        print(msg)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        sql_conn.close()
        return False

    moon_info = dict()
    raw_composition = json.loads(composition)

    # moon ores by typeid

    ubiquitous = list(range(45490, 45494)) + list(range(46280, 46287))
    common_ore = list(range(45494, 45498)) + list(range(46288, 46296))
    uncommon = list(range(45498, 45502)) + list(range(46296, 46303))
    rare = list(range(45502, 45507)) + list(range(46304, 46312))
    exceptional = list(range(45510, 45514)) + list(range(46312, 46320))

    # standard +15% ore varieties

    standard = list(range(46675, 46690))

    taxable_ore_list = ubiquitous + common_ore + uncommon + rare + exceptional
    taxable_ore_list.append(46287)


    # experimentally determined by folks to be 20,000 m^3/hr +/- a few m^3
    extraction_volume = 20000
    moon_value = 0
    taxable_value = 0
    count = 0
    composition_string = ''

    for ore in raw_composition.keys():

        # TOTAL isk/m^3 density
        isk_density = ore_data[ore]['density']
        # this makes the total volume of ore extracted
        ore_volume = extraction_volume * raw_composition[ore]
        moon_value += ore_volume * isk_density
        count += 1

        # build the composition string

        ratio = raw_composition[ore]
        ore_typeid = ore_data[ore]['typeID']

        # not every ore is taxed. currently only goo-bearing ores
        if ore_typeid in taxable_ore_list:
            taxable_value += ore_volume * isk_density

        composition_string += '{0}:{1}:{2},'.format(ore, ore_typeid, ratio)

    # trim trailing comma

    composition_string = composition_string[:-1]

    moon_info['taxable_value'] = round(taxable_value, 2)
    moon_info['moon_value'] = round(moon_value, 2)
    moon_info['composition'] = composition

    # store the moon data in mysql

    cursor = sql_conn.cursor()
    query = 'UPDATE MoonScans SET moon_value=%s, moongoo_ore_value=%s WHERE moonId=%s'

    try:
        cursor.execute(query, (
            moon_value,
            taxable_value,
            moon,
        ),)
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.ERROR)
        return False
    finally:
        cursor.close()
        sql_conn.commit()
        sql_conn.close()

    return

