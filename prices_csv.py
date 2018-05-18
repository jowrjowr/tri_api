import json
import math
import MySQLdb as mysql
import common.credentials.database as _database
from tri_core.common.moonprices import moon_scandata

def moon_csvprint():

    moon_scandata()

    # take the MoonValues data and print a useful CSV
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
    query = 'SELECT solarSystemName, planetNr, moonNr, constellationName, regionName, moon_value, moongoo_ore_value, oreComposition FROM MoonScans'

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

    # print CSV stuff
    print('system_name, planet, moon, constellation, region, total_value, taxable_value, ore1, ore1_ratio, ore2, ore2_ratio, ore3, ore3_ratio, ore4, ore4_ratio')

    for system_name, planet, moon, constellation, region, total_value, taxable_value, composition in rows:

        composition = json.loads(composition)
        csv_output = '{0},{1},{2},{3},{4},{5},{6},'.format(system_name, planet, moon, constellation, region, total_value, taxable_value)

        for ore in composition.keys():
            csv_output += '{0},{1},'.format(ore, composition[ore])

        print(csv_output[:-1])

moon_csvprint()
