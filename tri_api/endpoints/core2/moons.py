from ..core2 import blueprint
from .decorators import verify_user


ores = ["Flawless Arkonor", "Cubic Bistot", "Pellucid Crokite", "Jet Ochre",
        "Brilliant Gneiss",
        "Glazed Hedbergite", "Scintillating Hemorphite", "Pure Jaspet", "Resplendant Kernite",
        "Platinoid Omber",
        "Sparkling Plagioclase", "Opulent Pyroxeres", "Glossy Scordite", "Dazzling Spodumain",
        "Stable Veldspar",
        "Bitumens", "Coesite", "Sylvite", "Zeolites",
        "Cobaltite", "Euxenite", "Scheelite", "Titanite",
        "Chromite", "Otavite", "Sperrylite", "Vanadinite",
        "Carnotite", "Cinnabar", "Pollucite", "Zircon",
        "Loparite", "Monazite", "Xenotime", "Ytterbite"]

short = {
    "Flawless Arkonor": "ea",
    "Cubic Bistot": "eb",
    "Pellucid Crokite": "ec",
    "Jet Ochre": "edo",
    "Brilliant Gneiss": "eg",
    "Glazed Hedbergite": "ehg",
    "Scintillating Hemorphite": "ehp",
    "Pure Jaspet": "ej",
    "Resplendant Kernite": "ek",
    "Platinoid Omber": "eo",
    "Sparkling Plagioclase": "epl",
    "Opulent Pyroxeres": "epg",
    "Glossy Scordite": "esc",
    "Dazzling Spodumain": "esp",
    "Stable Veldspar": "ev",
    "Bitumens": "bi",
    "Coesite": "cs",
    "Sylvite": "sy",
    "Zeolites": "ze",
    "Cobaltite": "cb",
    "Euxenite": "eu",
    "Scheelite": "sc",
    "Titanite": "ti",
    "Chromite": "cr",
    "Otavite": "ot",
    "Sperrylite": "sp",
    "Vanadinite": "va",
    "Carnotite": "ca",
    "Cinnabar": "ci",
    "Pollucite": "po",
    "Zircon": "zi",
    "Loparite": "lo",
    "Monazite": "mo",
    "Xenotime": "xe",
    "Ytterbite": "yt"
}


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

    query = 'SELECT id,moonId,moonNr,planetNr,regionName,constellationName,solarSystemName,oreComposition,scannedByName,' \
            'scannedDate FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    moons = {}
    conflicts = {}

    for row in rows:
        ore_table = json.loads(row[7])

        for ore in ores:
            if ore not in ore_table:
                ore_table[ore] = float(0)

        for ore in ores:
            ore_table[short[ore]] = int(ore_table.pop(ore) * 100)

        if row[1] not in moons:
            moons[row[1]] = {
                'id': row[0],
                'moon_id': row[1],
                'region': row[4],
                'const': row[5],
                'system': row[6],
                'planet': row[3],
                'moon': row[2],
                'ore_composition': ore_table,
                'scanned_by': row[8],
                'scanned_date': row[9].isoformat(),
                'conflicted': False
            }
        else:
            moons[row[1]]['conflicted'] = True

            conflicts[row[0]] = {
                'id': row[0],
                'moon_id': row[1],
                'region': row[4],
                'const': row[5],
                'system': row[6],
                'planet': row[3],
                'moon': row[2],
                'ore_composition': ore_table,
                'scanned_by': row[8],
                'scanned_date': row[9].isoformat(),
                'conflicted': True
            }

    moon_list = []

    for moon_id in moons:
        moon_list.append(moons[moon_id])

    for entry_id in conflicts:
        moon_list.append(conflicts[entry_id])

    return flask.Response(json.dumps(moon_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/systems/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_systems(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import common.request_esi
    import flask
    import logging
    import MySQLdb as mysql
    import numpy
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

    query = 'SELECT id,moonId,moonNr,planetNr,regionName,constellationName,solarSystemId,solarSystemName,oreComposition,scannedByName,' \
            'scannedDate FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    systems = {}

    for row in rows:
        if row[6] in systems:
            ore_table = json.loads(row[8])

            for ore in ores:
                if ore not in ore_table:
                    ore_table[ore] = float(0)

            for ore in ores:
                ore_table[short[ore]] = numpy.ceil(ore_table.pop(ore) / 100) + systems[row[6]]['ore_count'][short[ore]]

            systems[row[6]]['ore_count'] = ore_table
            systems[row[6]]['scanned'] += 1
        else:
            ore_table = json.loads(row[8])

            for ore in ores:
                if ore not in ore_table:
                    ore_table[ore] = float(0)

            for ore in ores:
                ore_table[short[ore]] = numpy.ceil(ore_table.pop(ore)/100)

            systems[row[6]] = {
                'id': row[6],
                'region': row[4],
                'const': row[5],
                'system': row[7],
                'ore_count': ore_table,
                'moons': 0,
                'scanned': 1
            }

            request_system_url = 'universe/systems/{}/'.format(row[6])
            esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

            if not esi_system_code == 200:
                logger.error("/universe/systems/ API error {0}: {1}"
                             .format(esi_system_code, esi_system_result.get('error', 'N/A')))
                return flask.Response(json.dumps({'error': esi_system_result.get('error', 'esi error')}),
                                      status=500, mimetype='application/json')

            for planet in esi_system_result['planets']:
                systems[row[6]]['moons'] += len(planet.get('moons', []))

    system_list = []

    for system_id in systems:
        system_list.append(systems[system_id])

    return flask.Response(json.dumps(system_list), status=200, mimetype='application/json')


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

    from ._roman import fromRoman

    logger = logging.getLogger(__name__)

    lines = str(flask.request.get_json().get('text', "")).splitlines()

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

                moon['ore_composition'][str(match_mineral.group(1).strip())] = float(match_mineral.group(2))

                i += 1

            if 'system_id' in moon:
                import common.request_esi

                # get system details
                request_system_url = 'universe/systems/{}/'.format(moon['system_id'])
                esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

                if not esi_system_code == 200:
                    logger.error("/universe/systems/ API error {0}: {1}"
                                 .format(esi_system_code, esi_system_result.get('error', 'N/A')))
                    return flask.Response(json.dumps({'error': esi_system_result.get('error', 'esi error')}),
                                          status=500, mimetype='application/json')

                constellation_id = esi_system_result['constellation_id']

                # get constellation details
                request_const_url = 'universe/constellations/{}/'.format(constellation_id)
                esi_const_code, esi_const_result = common.request_esi.esi(__name__, request_const_url, method='get')

                if not esi_const_code == 200:
                    logger.error("/universe/constellations/ API error {0}: {1}"
                                 .format(esi_const_code, esi_const_result.get('error', 'N/A')))
                    return flask.Response(json.dumps({'error': esi_const_result.get('error', 'esi error')}),
                                          status=500, mimetype='application/json')

                constellation_name = esi_const_result['name']
                region_id = esi_const_result['region_id']

                # get region details
                request_region_url = 'universe/regions/{}/'.format(region_id)
                esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url, method='get')

                if not esi_region_code == 200:
                    logger.error("/universe/regions/ API error {0}: {1}"
                                 .format(esi_region_code, esi_region_result.get('error', 'N/A')))
                    return flask.Response(json.dumps({'error': esi_region_result.get('error', 'esi error')}),
                                          status=500, mimetype='application/json')

                region_name = esi_region_result['name']

                moon['const_id'] = constellation_id
                moon['const'] = constellation_name
                moon['region_id'] = region_id
                moon['region'] = region_name

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
                else:
                    import hashlib

                    hashes_saved = [hashlib.sha256(json.dumps(json.loads(row[0]), sort_keys=True).encode('utf-8')).hexdigest() for row in rows]
                    hash_new = hashlib.sha256(json.dumps(moon['ore_composition'], sort_keys=True).encode('utf-8')).hexdigest()

                    if hash_new in hashes_saved:
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
        'added': new_moons,
        'duplicates': old_moons,
        'conflicts': conflicts
    }), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/conflicts/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_conflicts(user_id):
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

    query = 'SELECT id,moonId,moonNr,planetNr,solarSystemName,oreComposition,scannedByName,scannedDate' \
            ' FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    moons = {}
    conflicts = {}

    for row in rows:
        ore_dict = json.loads(row[5])
        ore_list = []

        for key in ore_dict:
            ore_list.append("{0} {1}%".format(key, str(int(ore_dict[key]*100))))

        ore_list.sort()

        while len(ore_list) < 4:
            ore_list.append("-")

        if str(row[1]) in moons:
            if str(row[1]) not in conflicts:
                conflicts[moons[str(row[1])]['id']] = moons[str(row[1])]

            conflicts[str(row[0])] = {
                'id': row[0],
                'moon_id': row[1],
                'moon': row[2],
                'planet': row[3],
                'system': row[4],
                'ore_composition': ore_list,
                'scanned_by': row[6],
                'scanned_date': row[7].isoformat()
            }
        else:
            moons[str(row[1])] = {
                'id': row[0],
                'moon_id': row[1],
                'moon': row[2],
                'planet': row[3],
                'system': row[4],
                'ore_composition': ore_list,
                'scanned_by': row[6],
                'scanned_date': row[7].isoformat()
            }

    conflict_list = []

    for entry_id in conflicts:
        conflict_list.append(conflicts[entry_id])

    return flask.Response(json.dumps(conflict_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/coverage/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_coverage(user_id):
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

    query = 'SELECT moonId,regionId,regionName' \
            ' FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    moons = {}

    regions = {}

    for row in rows:
        moons[str(row[0])] = {
            'region_id': row[1],
            'region': row[2]
        }

    for moon_id in moons:
        regions[moons[moon_id]['region_id']] = {
            'region': moons[moon_id]['region'],
            'scanned': regions.get(moons[moon_id]['region_id'], {'scanned': 0})['scanned'] + 1
        }

    def get_moon_count(rid):
        import common.request_esi

        count = 0

        request_region_url = 'universe/regions/{}/'.format(rid)
        esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url, method='get')

        if not esi_region_code == 200:
            logger.error("/universe/regions/ API error {0}: {1}"
                         .format(esi_region_code, esi_region_result.get('error', 'N/A')))
            return flask.Response(json.dumps({'error': esi_region_result.get('error', 'esi error')}),
                                  status=500, mimetype='application/json')

        for constellation_id in esi_region_result['constellations']:
            request_const_url = 'universe/constellations/{}/'.format(constellation_id)
            esi_const_code, esi_const_result = common.request_esi.esi(__name__, request_const_url, method='get')

            if not esi_const_code == 200:
                logger.error("/universe/constellations/ API error {0}: {1}"
                             .format(esi_const_code, esi_const_result.get('error', 'N/A')))
                return flask.Response(json.dumps({'error': esi_const_result.get('error', 'esi error')}),
                                      status=500, mimetype='application/json')

            for system_id in esi_const_result['systems']:
                request_system_url = 'universe/systems/{}/'.format(system_id)
                esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

                if not esi_system_code == 200:
                    logger.error("/universe/systems/ API error {0}: {1}"
                                 .format(esi_system_code, esi_system_result.get('error', 'N/A')))
                    return flask.Response(json.dumps({'error': esi_system_result.get('error', 'esi error')}),
                                          status=500, mimetype='application/json')

                for planet in esi_system_result['planets']:
                    count += len(planet.get('moons', []))
        return count

    for region_id in regions:
        regions[region_id]['total'] = get_moon_count(region_id)
        regions[region_id]['coverage'] = int((regions[region_id]['scanned'] / regions[region_id]['total']) * 100)

    region_list = []

    for region_id in regions:
        region_list.append(regions[region_id])

    return flask.Response(json.dumps(region_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/scanners/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_scanners(user_id):
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

    query = 'SELECT scannedByName FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    scanners = {}

    for row in rows:
        scanner = row[0]
        scanners[scanner] = scanners.get(scanner, 0) + 1

    scanner_list = []

    for scanner in scanners:
        scanner_list.append({
            'scanner': scanner,
            'count': scanners[scanner]
        })

    return flask.Response(json.dumps(scanner_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/conflicts/resolve/<int:entry_id>/', methods=['POST'])
@verify_user(groups=['board'])
def moons_post_conflicts_resolve(user_id, entry_id):
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

    query = 'SELECT moonId FROM MoonScans WHERE id=%s'
    try:
        _ = cursor.execute(query, (entry_id,))
        rows = cursor.fetchall()
    except mysql.Error as error:
        cursor.close()

        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')

    moon_id = rows[0][0]

    query = 'SELECT id FROM MoonScans WHERE moonId=%s'
    try:
        _ = cursor.execute(query, (moon_id,))
        rows = cursor.fetchall()
    except mysql.Error as error:
        cursor.close()

        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')

    affected = [row[0] for row in rows]

    query = 'DELETE FROM MoonScans WHERE moonId=%s AND id<>%s'
    try:
        rowc = cursor.execute(query, (moon_id, entry_id))
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()
        sql_conn.commit()
        sql_conn.close()

    result = {
        'affected': affected
    }

    return flask.Response(json.dumps(result), status=200, mimetype='application/json')
