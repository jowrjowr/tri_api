from ..core2 import blueprint
from .decorators import verify_user


def get_system_details(system_id, logger=None):
    import common.request_esi
    import logging

    if logger is None:
        logger = logging.getLogger(__name__)

    # get system details
    request_system_url = 'universe/systems/{}/'.format(system_id)
    esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

    if not esi_system_code == 200:
        logger.error("/universe/systems/ API error {0}: {1}"
                     .format(esi_system_code, esi_system_result.get('error', 'N/A')))
        return None

    constellation_id = esi_system_result['constellation_id']

    # get constellation details
    request_const_url = 'universe/constellations/{}/'.format(constellation_id)
    esi_const_code, esi_const_result = common.request_esi.esi(__name__, request_const_url, method='get')

    if not esi_const_code == 200:
        logger.error("/universe/constellations/ API error {0}: {1}"
                     .format(esi_const_code, esi_const_result.get('error', 'N/A')))
        return None

    constellation_name = esi_const_result['name']
    region_id = esi_const_result['region_id']

    # get region details
    request_region_url = 'universe/regions/{}/'.format(region_id)
    esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url, method='get')

    if not esi_region_code == 200:
        logger.error("/universe/regions/ API error {0}: {1}"
                     .format(esi_region_code, esi_region_result.get('error', 'N/A')))
        return None

    region_name = esi_region_result['name']

    return {
        'const_id': constellation_id,
        'const': constellation_name,
        'region_id': region_id,
        'region': region_name
    }


def get_mineral_table(ore_composition):

    ores = ["Extracted Arkonor", "Extracted Bistot", "Extracted Crokite", "Extracted Dark Ochre", "Extracted Gneiss",
            "Extracted Hedbergite", "Extracted Hemorphite", "Extracted Jaspet", "Extracted Kernite", "Extracted Omber",
            "Extracted Plagioclase", "Extracted Pyroxeres", "Extracted Scordite", "Extracted Spodumain",
            "Extracted Veldspar",
            "Cobaltite", "Euxenite", "Scheelite", "Titanite",
            "Chromite", "Otavite", "Sperrylite", "Vanadinite",
            "Bitumens", "Coesite", "Sylvite", "Zeolites",
            "Carnotite","Cinnabar", "Pollucite", "Zircon",
            "Loparite", "Monazite", "Xenotime", "Ytterbite"]

    for ore in ores:
        if ore not in ore_composition:
            ore_composition[ore] = float(0)

    return ore_composition


@blueprint.route('/<int:user_id>/moons/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json

    logger = logging.getLogger(__name__)

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')

    cursor = sql_conn.cursor()

    query = 'SELECT id,moonNr,planetNr,regionName,constellationName,solarSystemName,oreComposition,scannedByName,' \
            'scannedDate FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    moons = []

    for row in rows:
        moon = {
            'entry_id': row[0],
            'region': row[3],
            'const': row[4],
            'system': row[5],
            'planet': row[2],
            'moon': row[1],
            'ore_composition': get_mineral_table(json.loads(row[6])),
            'scanned_by': row[7],
            'scanned_date': row[8].isoformat()
        }

        moons.append(moon)

    return flask.Response(json.dumps(moons), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/', methods=['POST'])
@verify_user(groups=['board', 'administation', 'triprobers'])
def moons_post(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json
    import re

    from .roman import fromRoman

    logger = logging.getLogger(__name__)

    lines = str(flask.request.get_data().decode("utf-8")).splitlines()

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")
    regex_win = re.compile("\\t(.*)\\t([0-9]\.[0-9]+)\\t([0-9]+)\\t([0-9]+)\\t([0-9]+)\\t([0-9]+)")

    moons = []

    for i in range(0, len(lines)):
        match = regex_moon.match(lines[i])

        if match:
            moon = {
                'system': match.group(1).strip(),
                'planet': int(fromRoman(match.group(3))),
                'moon': int(match.group(4)),
                'ore_composition': {},
                'valid': False
            }

            for j in range(1, 5):
                match_mineral = regex_win.match(lines[i + 1])

                if not match_mineral:
                    logger.warning('no regex match for line: {0} (if this is a new moon ignore)'.format(lines[i + 1]))
                    break

                moon['valid'] = True

                moon['system_id'] = int(match_mineral.group(4))
                moon['planet_id'] = int(match_mineral.group(5))
                moon['moon_id'] = int(match_mineral.group(6))

                moon['ore_composition'][match_mineral.group(1).strip()] = float(match_mineral.group(2))

                i += 1

            if 'system_id' in moon:
                location_info = get_system_details(moon['system_id'], logger=logger)

                if location_info is not None:
                    moon.update(location_info)

            moons.append(moon)

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')

    cursor = sql_conn.cursor()

    new_moons = 0
    old_moons = 0
    conflicts = 0

    try:
        for moon in moons:
            if moon['valid']:
                scanned_by_name = _ldaphelpers.ldap_uid2name(__name__, int(user_id))['characterName']

                # check if entry already exists
                rowc = cursor.execute("SELECT oreComposition FROM MoonScans WHERE moonId = %s", (moon['moon_id'],))
                rows = cursor.fetchall()

                if rowc == 0:
                    new_moons += 1

                    cursor.execute("INSERT INTO MoonScans "
                                   "(moonId, moonNr, planetId, planetNr, regionId, "
                                   "regionName, constellationId, constellationName, solarSystemId, solarSystemName,"
                                   "oreComposition, scannedBy, scannedByName, scannedDate) VALUES "
                                   "(%s, %s, %s, %s, %s,"
                                   "%s, %s, %s, %s, %s,"
                                   "%s, %s, %s, NOW())",
                                   (moon['moon_id'], moon['moon'], moon['planet_id'], moon['planet'], moon['region_id'],
                                    moon['region'], moon['const_id'], moon['const'], moon['system_id'], moon['system'],
                                    json.dumps(moon['ore_composition']), int(user_id), scanned_by_name))
                elif rowc == 1:
                    import hashlib

                    hash_saved = hashlib.sha256(json.dumps(json.loads(rows[0][0]), sort_keys=True).encode('utf-8')).hexdigest()
                    hash_new = hashlib.sha256(json.dumps(moon['ore_composition'], sort_keys=True).encode('utf-8')).hexdigest()

                    print(hash_saved)
                    print(hash_new)

                    if hash_new == hash_saved:
                        old_moons += 1
                    else:
                        conflicts += 1

                        logger.warning("moon conflict detected (id={0})".format(moon['moon_id']))

                        cursor.execute("INSERT INTO MoonScans "
                                       "(moonId, moonNr, planetId, planetNr, regionId, "
                                       "regionName, constellationId, constellationName, solarSystemId, solarSystemName,"
                                       "oreComposition, scannedBy, scannedByName, scannedDate) VALUES "
                                       "(%s, %s, %s, %s, %s,"
                                       "%s, %s, %s, %s, %s,"
                                       "%s, %s, %s, NOW())",
                                       (moon['moon_id'], moon['moon'], moon['planet_id'], moon['planet'],
                                        moon['region_id'],
                                        moon['region'], moon['const_id'], moon['const'], moon['system_id'],
                                        moon['system'],
                                        json.dumps(moon['ore_composition']), int(user_id), scanned_by_name))
                else:
                    raise mysql.Error("database error (identical moons detected)")
            else:
                print(json.dumps(moon))
    except mysql.Error as error:
        sql_conn.rollback()
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()
        sql_conn.commit()
        sql_conn.close()

    return flask.Response(json.dumps({
        'moons_added': new_moons,
        'moons_not_added': old_moons,
        'moons_conflicted': conflicts
    }), status=200, mimetype='application/json')
