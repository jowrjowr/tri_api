from ..core2 import blueprint
from .decorators import verify_user


ores = ["Flawless Arkonor", "Cubic Bistot", "Pellucid Crokite", "Jet Ochre",
        "Brilliant Gneiss",
        "Lustrous Hedbergite", "Scintillating Hemorphite", "Immaculate Jaspet", "Resplendant Kernite",
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
    "Lustrous Hedbergite": "ehg",
    "Scintillating Hemorphite": "ehp",
    "Immaculate Jaspet": "ej",
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

    from common.logger import securitylog

    securitylog(__name__, 'viewed moon scan',
                ipaddress=flask.request.headers['X-Real-Ip'],
                charid=user_id)

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

    query = 'SELECT id,moonId,moonNr,planetId,planetNr,regionId,regionName,constellationId,constellationName,' \
            'solarSystemId,solarSystemName,oreComposition,scannedByName,scannedDate FROM MoonScans'
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
        ore_table = json.loads(row[11])

        for ore in ores:
            if ore not in ore_table:
                ore_table[ore] = float(0)

        for ore in ores:
            ore_table[short[ore]] = float(ore_table.pop(ore))

        if row[1] not in moons:
            moons[row[1]] = {
                'id': row[0],
                'moon_id': row[1],
                'moon': row[2],
                'planet_id': row[3],
                'planet': row[4],
                'region_id': row[5],
                'region': row[6],
                'const_id': row[7],
                'const': row[8],
                'system_id': row[9],
                'system': row[10],
                'ore_composition': ore_table,
                'scanned_by': row[12],
                'scanned_date': row[13].isoformat(),
                'conflicted': False
            }
        else:
            moons[row[1]]['conflicted'] = True

            conflicts[row[0]] = {
                'id': row[0],
                'moon_id': row[1],
                'moon': row[2],
                'planet_id': row[3],
                'planet': row[4],
                'region_id': row[5],
                'region': row[6],
                'const_id': row[7],
                'const': row[8],
                'system_id': row[9],
                'system': row[10],
                'ore_composition': ore_table,
                'scanned_by': row[12],
                'scanned_date': row[13].isoformat(),
                'conflicted': False
            }

    moon_list = []

    for moon_id in moons:
        moon_list.append(moons[moon_id])

    for entry_id in conflicts:
        moon_list.append(conflicts[entry_id])

    return flask.Response(json.dumps(moon_list), status=200, mimetype='application/json')


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


@blueprint.route('/<int:user_id>/moons/missing/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_missing(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import common.request_esi
    import flask
    import logging
    import MySQLdb as mysql
    import numpy
    import json
    import re

    from ._roman import fromRoman
    from concurrent.futures import ThreadPoolExecutor, as_completed

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

    query = 'SELECT id,moonId,moonNr,planetNr,regionName,constellationId,constellationName,solarSystemId,' \
            'solarSystemName,oreComposition,scannedByName,scannedDate FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    constellations = {}

    for row in rows:
        if row[5] not in constellations:
            constellations[row[5]] = {
                'region': row[4],
                'const': row[6],
                'scanned': [row[1]],
                'moons': []
            }
        else:
            constellations[row[5]]['scanned'].append(row[1])

    def get_moonlist(const_id):
        moonlist = []

        request_const_url = 'universe/constellations/{}/'.format(const_id)
        esi_const_code, esi_const_result = common.request_esi.esi(__name__, request_const_url, method='get')

        if not esi_const_code == 200:
            logger.error("/universe/constellations/ API error {0}: {1}"
                         .format(esi_const_result, esi_const_code.get('error', 'N/A')))
            return flask.Response(json.dumps({'error': esi_const_result.get('error', 'esi error')}),
                                  status=500, mimetype='application/json')

        for system_id in esi_const_result["systems"]:
            request_system_url = 'universe/systems/{}/'.format(system_id)
            esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

            if not esi_system_code == 200:
                logger.error("/universe/systems/ API error {0}: {1}"
                             .format(esi_system_code, esi_system_result.get('error', 'N/A')))
                return flask.Response(json.dumps({'error': esi_system_result.get('error', 'esi error')}),
                                      status=500, mimetype='application/json')

            for planet in esi_system_result['planets']:
                moonlist.extend(planet.get('moons', []))

        return moonlist

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_moonlist, const_id): const_id for const_id in constellations}

        for future in as_completed(futures):
            const_id = futures[future]
            constellations[const_id]["moons"] = future.result()

    moons = {}

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")

    for const_id in constellations:
        for moon_id in constellations[const_id]['moons']:
            if moon_id not in constellations[const_id]['scanned']:
                moons[moon_id] = {
                    'id': moon_id,
                    'region': constellations[const_id]['region'],
                    'const': constellations[const_id]['const'],
                }

    def get_moonname(moon_id_internal):
        moon = {}

        request_moon_url = 'universe/moons/{}/'.format(moon_id_internal)
        esi_moon_code, esi_moon_result = common.request_esi.esi(__name__, request_moon_url, method='get')

        if not esi_moon_code == 200:
            logger.error("/universe/moons/ API error {0}: {1}"
                         .format(esi_moon_code, esi_moon_result.get('error', 'N/A')))
            return None

        match = regex_moon.match(esi_moon_result['name'])

        if match:
            moon['system'] = match.group(1).strip()
            moon['planet'] = int(fromRoman(match.group(2) + match.group(3)))
            moon['moon'] = int(match.group(4))
        else:
            logger.error("/universe/moons/ API bad result (no regex match) {0}: {1}"
                         .format(esi_moon_code, esi_moon_result.get('error', 'N/A')))
            return None

        return moon

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_moonname, moon_id): moon_id for moon_id in moons}

        for future in as_completed(futures):
            moon_id = futures[future]
            moons[moon_id].update(future.result())

    moon_list = []

    for moon_id in moons:
        moon_list.append(moons[moon_id])

    return flask.Response(json.dumps(moon_list), status=200, mimetype='application/json')


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

    scanner_list = sorted(scanner_list, key=lambda d: d['count'], reverse=True)

    return flask.Response(json.dumps(scanner_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/structures/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_structures(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json
    import re

    from common.logger import securitylog
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ._roman import fromRoman

    securitylog(__name__, 'viewed moon structures',
                ipaddress=flask.request.headers['X-Real-Ip'],
                charid=user_id)

    logger = logging.getLogger(__name__)

    # get all characters that access & necessary scopes to structures
    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(esiScope=esi-corporations.read_structures.v1)' \
                '(esiScope=esi-universe.read_structures.v1)(corporationRole=Director)' \
                '(esiAccessToken=*))'
    attrlist = ['uid', 'corporation', 'esiScope']

    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if not code:
        logger.error("unable to fetch ldap information")
        return flask.Response(json.dumps({'error': "ldap error"}),
                              status=500, mimetype='application/json')

    corporations = {}

    for cn in result:
        if result[cn]["corporation"] not in corporations:
            corporations[result[cn]["corporation"]] = {
                "character_id": result[cn]["uid"]
            }

            if 'esi-industry.read_corporation_mining.v1' in result[cn]["esiScope"]:
                corporations[result[cn]["corporation"]]["read_extraction"] = True
            else:
                corporations[result[cn]["corporation"]]["read_extraction"] = False

        elif not corporations[result[cn]["corporation"]]["read_extraction"]:
            if 'esi-industry.read_corporation_mining.v1' in result[cn]["esiScope"]:
                corporations[result[cn]["corporation"]]["character_id"] = result[cn]["uid"]
                corporations[result[cn]["corporation"]]["read_extraction"] = True

    def get_structures(char_id, corp_id):
        import common.request_esi

        request_structures_url = 'corporations/{}/structures/'.format(corp_id)
        esi_structures_code, esi_structures_result = common.request_esi.esi(__name__, request_structures_url, method='get',
                                                                    charid=char_id)

        if not esi_structures_code == 200:
            logger.error("/corporations/<corporation_id>/structures/ API error {0}: {1}"
                         .format(esi_structures_code, esi_structures_result.get('error', 'N/A')))
            return None

        return esi_structures_result

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structures, corporations[corp_id]["character_id"], corp_id): corp_id for corp_id in corporations}
        for future in as_completed(futures):
            corp_id = futures[future]
            corporations[corp_id]["structures"] = future.result()

    structures = {}

    for corp_id in corporations:
        for structure in corporations[corp_id]["structures"]:
            if structure["type_id"] in [35835, 35836]:
                if "services" in structure:
                    valid_drill = False

                    for service in structure["services"]:
                        if service["name"] == "Moon Drilling":
                            valid_drill = True
                    if valid_drill:
                        structures[structure["structure_id"]] = structure
                        structures[structure["structure_id"]]["character_id"] = corporations[corp_id]["character_id"]

                        structures[structure["structure_id"]]["chunk_arrival"] = ""
                        structures[structure["structure_id"]]["chunk_decay"] = ""

                        if structure["type_id"] == 35835:
                            structures[structure["structure_id"]]["type_name"] = "Athanor"
                        elif structure["type_id"] == 35836:
                            structures[structure["structure_id"]]["type_name"] = "Tatara"

    def get_structure_extractions(char_id, corp_id):
        import common.request_esi

        request_extractions_url = 'corporation/{}/mining/extractions/'.format(corp_id)
        esi_extractions_code, esi_extractions_result = common.request_esi.esi(__name__, request_extractions_url,
                                                                            method='get',
                                                                            charid=char_id)

        if not esi_extractions_code == 200:
            logger.error("/corporation/<corporation_id>/mining/extractions/ API error {0}: {1}"
                         .format(esi_extractions_code, esi_extractions_result.get('error', 'N/A')))
            return None

        return esi_extractions_result

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structure_extractions, corporations[corp_id]["character_id"], corp_id):
                       corp_id for corp_id in dict((k, v) for k, v in corporations.items() if v["read_extraction"] is True)}
        for future in as_completed(futures):
            extractions = future.result()

            for extraction in extractions:
                if extraction["structure_id"] in structures:
                    structures[extraction["structure_id"]]["chunk_arrival"] = extraction["chunk_arrival_time"]
                    structures[extraction["structure_id"]]["chunk_decay"] = extraction["chunk_arrival_time"]

    def get_structure_info(_char_id, structure_id):
        import common.request_esi

        request_structures_url = 'universe/structures/{}/'.format(structure_id)
        esi_structures_code, esi_structures_result = common.request_esi.esi(__name__, request_structures_url,
                                                                            method='get',
                                                                            charid=_char_id)

        if not esi_structures_code == 200:
            logger.error("/universe/structures/<structure_id>/ API error {0}: {1}"
                         .format(esi_structures_code, esi_structures_result.get('error', 'N/A')))
            return None

        return esi_structures_result["name"], esi_structures_result["position"]

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structure_info, structures[structure_id]["character_id"], structure_id): structure_id for structure_id in structures}
        for future in as_completed(futures):
            structure_id = futures[future]

            structures[structure_id]["name"], structures[structure_id]["position"] = future.result()

    systems = {}

    def get_moons(_system_id):
        import common.request_esi

        request_system_url = 'universe/systems/{}/'.format(_system_id)
        esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

        if not esi_system_code == 200:
            logger.error("/universe/systems/ API error {0}: {1}"
                         .format(esi_system_code, esi_system_result.get('error', 'N/A')))
            return None

        moons = []

        for planet in esi_system_result["planets"]:
            moons.extend(planet.get("moons", []))

        return moons

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_moons, structures[structure_id]["system_id"]): structure_id for structure_id in structures}
        for future in as_completed(futures):
            system_id = structures[futures[future]]["system_id"]
            result = future.result()

            if result is not None:
                if system_id in systems:
                    for moon_id in result:
                        systems[system_id]["moons"][moon_id] = {}
                else:
                    systems[system_id] = {
                        "moons": {}
                    }

                    for moon_id in result:
                        systems[system_id]["moons"][moon_id] = {}

    def get_system_info(_system_id):
        import common.request_esi

        _result = {}

        request_system_url = 'universe/systems/{}/'.format(_system_id)
        esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

        if not esi_system_code == 200:
            logger.error("/universe/systems/ API error {0}: {1}"
                         .format(esi_system_code, esi_system_result.get('error', 'N/A')))
            return _result

        _result["system"] = esi_system_result["name"]

        request_constellation_url = 'universe/constellations/{}/'.format(esi_system_result["constellation_id"])
        esi_constellation_code, esi_constellation_result = common.request_esi.esi(__name__, request_constellation_url, method='get')

        if not esi_constellation_code == 200:
            logger.error("/universe/constellations/ API error {0}: {1}"
                         .format(esi_constellation_code, esi_constellation_result.get('error', 'N/A')))
            return _result

        _result["const"] = esi_constellation_result["name"]

        request_region_url = 'universe/regions/{}/'.format(esi_constellation_result["region_id"])
        esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url,
                                                                                  method='get')

        if not esi_region_code == 200:
            logger.error("/universe/constellations/ API error {0}: {1}"
                         .format(esi_region_code, esi_region_result.get('error', 'N/A')))
            return _result

        _result["region"] = esi_region_result["name"]

        return _result

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_system_info, system_id): system_id for system_id in systems}
        for future in as_completed(futures):
            system_id = futures[future]
            result = future.result()

            systems[system_id]["region"] = result.get("region", "N/A")
            systems[system_id]["const"] = result.get("const", "N/A")
            systems[system_id]["system"] = result.get("system", "N/A")

    def get_moon_position(_moon_id):
        import common.request_esi

        request_moon_url = 'universe/moons/{}/'.format(_moon_id)
        esi_moon_code, esi_moon_result = common.request_esi.esi(__name__, request_moon_url, method='get')

        if not esi_moon_code == 200:
            logger.error("/universe/moons/ API error {0}: {1}"
                         .format(esi_moon_code, esi_moon_result.get('error', 'N/A')))
            return None

        return esi_moon_result["name"], esi_moon_result["position"]

    for system_id in systems:
        with ThreadPoolExecutor(10) as executor:
            futures = {executor.submit(get_moon_position, moon_id): moon_id for moon_id in systems[system_id]["moons"]}
            for future in as_completed(futures):
                moon_id = futures[future]
                result = future.result()

                systems[system_id]["moons"][moon_id]["name"], systems[system_id]["moons"][moon_id]["position"] = result

    def get_structure_owner(_corp_id):
        import common.request_esi

        request_corporation_url = 'corporations/{}/'.format(_corp_id)
        esi_corporation_code, esi_corporation_result = common.request_esi.esi(__name__, request_corporation_url, method='get')

        if not esi_corporation_code == 200:
            logger.error("/corporations/<corporation_id>/ API error {0}: {1}"
                         .format(esi_corporation_code, esi_corporation_result.get('error', 'N/A')))
            return "N/A", "N/A"

        if "alliance_id" in esi_corporation_result:
            request_alliance_url = 'alliances/{}/'.format(esi_corporation_result["alliance_id"])
            esi_alliance_code, esi_alliance_result = common.request_esi.esi(__name__, request_alliance_url,
                                                                                  method='get')

            if not esi_alliance_code == 200:
                logger.error("/alliances/<alliance_id>/ API error {0}: {1}"
                             .format(esi_alliance_code, esi_alliance_result.get('error', 'N/A')))
                return esi_corporation_result["corporation_name"], "N/A"

            return esi_alliance_result["alliance_name"], esi_corporation_result["corporation_name"]
        else:
            return "", esi_corporation_result["corporation_name"]

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structure_owner, structures[structure_id]["corporation_id"]): structure_id for structure_id in structures}
        for future in as_completed(futures):
            structure_id = futures[future]

            structures[structure_id]["alliance"], structures[structure_id]["corporation"] = future.result()

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")

    for structure_id in structures:
        import numpy as np

        structure = structures[structure_id]

        # find nearest moon
        structure_system_id = structure["system_id"]

        structure["region"] = systems[structure_system_id]["region"]
        structure["const"] = systems[structure_system_id]["const"]
        structure["system"] = systems[structure_system_id]["system"]

        structure_moon_id = None
        structure_moon_name = None
        structure_moon_distance2 = 1e30

        for moon_id in systems[structure_system_id]["moons"]:
            moon = systems[structure_system_id]["moons"][moon_id]

            distance2 = (moon["position"]["x"]-structure["position"]["x"])**2 + \
                        (moon["position"]["y"]-structure["position"]["y"])**2 + \
                        (moon["position"]["z"]-structure["position"]["z"])**2

            if distance2 < structure_moon_distance2:
                structure_moon_id = moon_id
                structure_moon_name = moon["name"]
                structure_moon_distance2 = distance2

        if structure_moon_id is None:
            structure["planet"] = "N/A"
            structure["moon"] = "N/A"
            structure["distance"] = "N/A"
        else:
            match = regex_moon.match(structure_moon_name)

            if match:
                structure['planet'] = int(fromRoman(match.group(2) + match.group(3)))
                structure['moon'] = int(match.group(4))
            else:
                logger.error("regex matching for moon name failed")
                structure["planet"] = "N/A"
                structure["moon"] = "N/A"

            structure["distance"] = np.sqrt(structure_moon_distance2)

    structure_list = []

    for structure_id in structures:
        structure_list.append(structures[structure_id])

    return flask.Response(json.dumps(structure_list),
                          status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/structures/corp/', methods=['GET'])
@verify_user(groups=['triumvirate'])
def moons_get_structure_cycles(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json
    import re

    from common.logger import securitylog
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ._roman import fromRoman

    securitylog(__name__, 'viewed corp moon structures',
                ipaddress=flask.request.headers['X-Real-Ip'],
                charid=user_id)

    logger = logging.getLogger(__name__)

    # get corporation id
    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(uid={})'.format(user_id)
    attrlist = ['corporation']

    code, result_user = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if not code:
        logger.error("unable to fetch ldap information")
        return flask.Response(json.dumps({'error': "ldap error"}),
                              status=500, mimetype='application/json')

    (dn, info), = result_user.items()

    corporation = info['corporation']

    # get all characters that access & necessary scopes to structures
    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(esiScope=esi-corporations.read_structures.v1)' \
                '(esiScope=esi-universe.read_structures.v1)(corporationRole=Director)' \
                '(esiAccessToken=*)(corporation={}))'.format(corporation)
    attrlist = ['uid', 'corporation', 'esiScope']

    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if not code:
        logger.error("unable to fetch ldap information")
        return flask.Response(json.dumps({'error': "ldap error"}),
                              status=500, mimetype='application/json')

    corporations = {}

    for cn in result:
        if result[cn]["corporation"] not in corporations:
            corporations[result[cn]["corporation"]] = {
                "character_id": result[cn]["uid"]
            }

            if 'esi-industry.read_corporation_mining.v1' in result[cn]["esiScope"]:
                corporations[result[cn]["corporation"]]["read_extraction"] = True
            else:
                corporations[result[cn]["corporation"]]["read_extraction"] = False

        elif not corporations[result[cn]["corporation"]]["read_extraction"]:
            if 'esi-industry.read_corporation_mining.v1' in result[cn]["esiScope"]:
                corporations[result[cn]["corporation"]]["character_id"] = result[cn]["uid"]
                corporations[result[cn]["corporation"]]["read_extraction"] = True

    def get_structures(char_id, corp_id):
        import common.request_esi

        request_structures_url = 'corporations/{}/structures/'.format(corp_id)
        esi_structures_code, esi_structures_result = common.request_esi.esi(__name__, request_structures_url, method='get',
                                                                    charid=char_id)

        if not esi_structures_code == 200:
            logger.error("/corporations/<corporation_id>/structures/ API error {0}: {1}"
                         .format(esi_structures_code, esi_structures_result.get('error', 'N/A')))
            return None

        return esi_structures_result

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structures, corporations[corp_id]["character_id"], corp_id): corp_id for corp_id in corporations}
        for future in as_completed(futures):
            corp_id = futures[future]
            corporations[corp_id]["structures"] = future.result()

    structures = {}

    for corp_id in corporations:
        for structure in corporations[corp_id]["structures"]:
            if structure["type_id"] in [35835, 35836]:
                if "services" in structure:
                    valid_drill = False

                    for service in structure["services"]:
                        if service["name"] == "Moon Drilling":
                            valid_drill = True
                    if valid_drill:
                        structures[structure["structure_id"]] = structure
                        structures[structure["structure_id"]]["character_id"] = corporations[corp_id]["character_id"]

                        structures[structure["structure_id"]]["chunk_arrival"] = ""
                        structures[structure["structure_id"]]["chunk_decay"] = ""

                        if structure["type_id"] == 35835:
                            structures[structure["structure_id"]]["type_name"] = "Athanor"
                        elif structure["type_id"] == 35836:
                            structures[structure["structure_id"]]["type_name"] = "Tatara"

    def get_structure_extractions(char_id, corp_id):
        import common.request_esi

        request_extractions_url = 'corporation/{}/mining/extractions/'.format(corp_id)
        esi_extractions_code, esi_extractions_result = common.request_esi.esi(__name__, request_extractions_url,
                                                                            method='get',
                                                                            charid=char_id)

        if not esi_extractions_code == 200:
            logger.error("/corporation/<corporation_id>/mining/extractions/ API error {0}: {1}"
                         .format(esi_extractions_code, esi_extractions_result.get('error', 'N/A')))
            return None

        return esi_extractions_result

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structure_extractions, corporations[corp_id]["character_id"], corp_id):
                       corp_id for corp_id in dict((k, v) for k, v in corporations.items() if v["read_extraction"] is True)}
        for future in as_completed(futures):
            extractions = future.result()

            for extraction in extractions:
                if extraction["structure_id"] in structures:
                    structures[extraction["structure_id"]]["chunk_arrival"] = extraction["chunk_arrival_time"]
                    structures[extraction["structure_id"]]["chunk_decay"] = extraction["chunk_arrival_time"]

    def get_structure_info(_char_id, structure_id):
        import common.request_esi

        request_structures_url = 'universe/structures/{}/'.format(structure_id)
        esi_structures_code, esi_structures_result = common.request_esi.esi(__name__, request_structures_url,
                                                                            method='get',
                                                                            charid=_char_id)

        if not esi_structures_code == 200:
            logger.error("/universe/structures/<structure_id>/ API error {0}: {1}"
                         .format(esi_structures_code, esi_structures_result.get('error', 'N/A')))
            return None

        return esi_structures_result["name"], esi_structures_result["position"]

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structure_info, structures[structure_id]["character_id"], structure_id): structure_id for structure_id in structures}
        for future in as_completed(futures):
            structure_id = futures[future]

            structures[structure_id]["name"], structures[structure_id]["position"] = future.result()

    systems = {}

    def get_moons(_system_id):
        import common.request_esi

        request_system_url = 'universe/systems/{}/'.format(_system_id)
        esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

        if not esi_system_code == 200:
            logger.error("/universe/systems/ API error {0}: {1}"
                         .format(esi_system_code, esi_system_result.get('error', 'N/A')))
            return None

        moons = []

        for planet in esi_system_result["planets"]:
            moons.extend(planet.get("moons", []))

        return moons

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_moons, structures[structure_id]["system_id"]): structure_id for structure_id in structures}
        for future in as_completed(futures):
            system_id = structures[futures[future]]["system_id"]
            result = future.result()

            if result is not None:
                if system_id in systems:
                    for moon_id in result:
                        systems[system_id]["moons"][moon_id] = {}
                else:
                    systems[system_id] = {
                        "moons": {}
                    }

                    for moon_id in result:
                        systems[system_id]["moons"][moon_id] = {}

    def get_system_info(_system_id):
        import common.request_esi

        _result = {}

        request_system_url = 'universe/systems/{}/'.format(_system_id)
        esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

        if not esi_system_code == 200:
            logger.error("/universe/systems/ API error {0}: {1}"
                         .format(esi_system_code, esi_system_result.get('error', 'N/A')))
            return _result

        _result["system"] = esi_system_result["name"]

        request_constellation_url = 'universe/constellations/{}/'.format(esi_system_result["constellation_id"])
        esi_constellation_code, esi_constellation_result = common.request_esi.esi(__name__, request_constellation_url, method='get')

        if not esi_constellation_code == 200:
            logger.error("/universe/constellations/ API error {0}: {1}"
                         .format(esi_constellation_code, esi_constellation_result.get('error', 'N/A')))
            return _result

        _result["const"] = esi_constellation_result["name"]

        request_region_url = 'universe/regions/{}/'.format(esi_constellation_result["region_id"])
        esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url,
                                                                                  method='get')

        if not esi_region_code == 200:
            logger.error("/universe/constellations/ API error {0}: {1}"
                         .format(esi_region_code, esi_region_result.get('error', 'N/A')))
            return _result

        _result["region"] = esi_region_result["name"]

        return _result

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_system_info, system_id): system_id for system_id in systems}
        for future in as_completed(futures):
            system_id = futures[future]
            result = future.result()

            systems[system_id]["region"] = result.get("region", "N/A")
            systems[system_id]["const"] = result.get("const", "N/A")
            systems[system_id]["system"] = result.get("system", "N/A")

    def get_moon_position(_moon_id):
        import common.request_esi

        request_moon_url = 'universe/moons/{}/'.format(_moon_id)
        esi_moon_code, esi_moon_result = common.request_esi.esi(__name__, request_moon_url, method='get')

        if not esi_moon_code == 200:
            logger.error("/universe/moons/ API error {0}: {1}"
                         .format(esi_moon_code, esi_moon_result.get('error', 'N/A')))
            return None

        return esi_moon_result["name"], esi_moon_result["position"]

    for system_id in systems:
        with ThreadPoolExecutor(10) as executor:
            futures = {executor.submit(get_moon_position, moon_id): moon_id for moon_id in systems[system_id]["moons"]}
            for future in as_completed(futures):
                moon_id = futures[future]
                result = future.result()

                systems[system_id]["moons"][moon_id]["name"], systems[system_id]["moons"][moon_id]["position"] = result

    def get_structure_owner(_corp_id):
        import common.request_esi

        request_corporation_url = 'corporations/{}/'.format(_corp_id)
        esi_corporation_code, esi_corporation_result = common.request_esi.esi(__name__, request_corporation_url, method='get')

        if not esi_corporation_code == 200:
            logger.error("/corporations/<corporation_id>/ API error {0}: {1}"
                         .format(esi_corporation_code, esi_corporation_result.get('error', 'N/A')))
            return "N/A", "N/A"

        if "alliance_id" in esi_corporation_result:
            request_alliance_url = 'alliances/{}/'.format(esi_corporation_result["alliance_id"])
            esi_alliance_code, esi_alliance_result = common.request_esi.esi(__name__, request_alliance_url,
                                                                                  method='get')

            if not esi_alliance_code == 200:
                logger.error("/alliances/<alliance_id>/ API error {0}: {1}"
                             .format(esi_alliance_code, esi_alliance_result.get('error', 'N/A')))
                return esi_corporation_result["corporation_name"], "N/A"

            return esi_alliance_result["alliance_name"], esi_corporation_result["corporation_name"]
        else:
            return "", esi_corporation_result["corporation_name"]

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_structure_owner, structures[structure_id]["corporation_id"]): structure_id for structure_id in structures}
        for future in as_completed(futures):
            structure_id = futures[future]

            structures[structure_id]["alliance"], structures[structure_id]["corporation"] = future.result()

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")

    for structure_id in structures:
        import numpy as np

        structure = structures[structure_id]

        # find nearest moon
        structure_system_id = structure["system_id"]

        structure["region"] = systems[structure_system_id]["region"]
        structure["const"] = systems[structure_system_id]["const"]
        structure["system"] = systems[structure_system_id]["system"]

        structure_moon_id = None
        structure_moon_name = None
        structure_moon_distance2 = 1e30

        for moon_id in systems[structure_system_id]["moons"]:
            moon = systems[structure_system_id]["moons"][moon_id]

            distance2 = (moon["position"]["x"]-structure["position"]["x"])**2 + \
                        (moon["position"]["y"]-structure["position"]["y"])**2 + \
                        (moon["position"]["z"]-structure["position"]["z"])**2

            if distance2 < structure_moon_distance2:
                structure_moon_id = moon_id
                structure_moon_name = moon["name"]
                structure_moon_distance2 = distance2

        if structure_moon_id is None:
            structure["planet"] = "N/A"
            structure["moon"] = "N/A"
            structure["distance"] = "N/A"
        else:
            match = regex_moon.match(structure_moon_name)

            if match:
                structure['planet'] = int(fromRoman(match.group(2) + match.group(3)))
                structure['moon'] = int(match.group(4))
            else:
                logger.error("regex matching for moon name failed")
                structure["planet"] = "N/A"
                structure["moon"] = "N/A"

            structure["distance"] = np.sqrt(structure_moon_distance2)

    structure_list = []

    for structure_id in structures:
        structure_list.append(structures[structure_id])

    return flask.Response(json.dumps(structure_list),
                          status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/regions/list/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_regions_list(user_id):
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

    query = 'SELECT regionId,regionName FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    regions = {}
    conflicts = {}

    for row in rows:
        regions[row[0]] = {
            "region_id": row[0],
            "region": row[1]
        }

    region_list = []

    for region_id in regions:
        region_list.append(regions[region_id])

    return flask.Response(json.dumps(region_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/regions/<int:region_id>/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_regions_moons(user_id, region_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json

    from common.logger import securitylog

    securitylog(__name__, 'viewed region {0} moon scan'.format(region_id),
                ipaddress=flask.request.headers['X-Real-Ip'],
                charid=user_id)

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

    query = 'SELECT id,moonId,moonNr,planetId,planetNr,regionId,regionName,constellationId,constellationName,' \
            'solarSystemId,solarSystemName,oreComposition,scannedByName,scannedDate FROM MoonScans WHERE ' \
            'regionId=%s'

    try:
        _ = cursor.execute(query, (region_id,))
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    moons = {}
    conflicts = {}

    for row in rows:
        ore_table = json.loads(row[11])

        for ore in ores:
            if ore not in ore_table:
                ore_table[ore] = float(0)

        for ore in ores:
            ore_table[short[ore]] = float(ore_table.pop(ore))

        ore_summary = {
            "hso": ore_table["ev"] + ore_table["esc"] + ore_table["epg"] + ore_table["epl"] + ore_table["eo"] + ore_table["ek"],
            "lso": ore_table["ej"] + ore_table["ehp"] + ore_table["ehg"],
            "nso": ore_table["ea"] + ore_table["eb"] + ore_table["ec"] + ore_table["edo"] + ore_table["eg"] + ore_table["esp"],
            "r0": ore_table["bi"] + ore_table["cs"] + ore_table["sy"] + ore_table["ze"],
            "r8": ore_table["cb"] + ore_table["eu"] + ore_table["sc"] + ore_table["ti"],
            "r16": ore_table["cr"] + ore_table["ot"] + ore_table["sp"] + ore_table["va"],
            "r32": ore_table["ca"] + ore_table["ci"] + ore_table["po"] + ore_table["zi"],
            "r64": ore_table["lo"] + ore_table["mo"] + ore_table["xe"] + ore_table["yt"]
        }

        if row[1] not in moons:
            moons[row[1]] = {
                'id': row[0],
                'moon_id': row[1],
                'moon': row[2],
                'planet_id': row[3],
                'planet': row[4],
                'region_id': row[5],
                'region': row[6],
                'const_id': row[7],
                'const': row[8],
                'system_id': row[9],
                'system': row[10],
                'ore_composition': ore_table,
                'ore_summary': ore_summary,
                'scanned_by': row[12],
                'scanned_date': row[13].isoformat(),
                'conflicted': False
            }
        else:
            moons[row[1]]['conflicted'] = True

            conflicts[row[0]] = {
                'id': row[0],
                'moon_id': row[1],
                'moon': row[2],
                'planet_id': row[3],
                'planet': row[4],
                'region_id': row[5],
                'region': row[6],
                'const_id': row[7],
                'const': row[8],
                'system_id': row[9],
                'system': row[10],
                'ore_composition': ore_table,
                'ore_summary': ore_summary,
                'scanned_by': row[12],
                'scanned_date': row[13].isoformat(),
                'conflicted': False
            }

    moon_list = []

    for moon_id in moons:
        moon_list.append(moons[moon_id])

    for entry_id in conflicts:
        moon_list.append(conflicts[entry_id])

    return flask.Response(json.dumps(moon_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/regions/summary/', methods=['GET'])
@verify_user(groups=['board'])
def moons_get_regions_summary(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json

    from concurrent.futures import ThreadPoolExecutor, as_completed

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

    query = 'SELECT regionId,regionName,oreComposition FROM MoonScans'
    try:
        _ = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as error:
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        cursor.close()

    regions = {}

    for row in rows:
        ore_table = json.loads(row[2])

        for ore in ores:
            if ore not in ore_table:
                ore_table[ore] = float(0)

        for ore in ores:
            ore_table[short[ore]] = float(ore_table.pop(ore))

        ore_summary = {
            "hso": ore_table["ev"] + ore_table["esc"] + ore_table["epg"] + ore_table["epl"] + ore_table["eo"] +
                   ore_table["ek"],
            "lso": ore_table["ej"] + ore_table["ehp"] + ore_table["ehg"],
            "nso": ore_table["ea"] + ore_table["eb"] + ore_table["ec"] + ore_table["edo"] + ore_table["eg"] + ore_table[
                "esp"],
            "r0": ore_table["bi"] + ore_table["cs"] + ore_table["sy"] + ore_table["ze"],
            "r8": ore_table["cb"] + ore_table["eu"] + ore_table["sc"] + ore_table["ti"],
            "r16": ore_table["cr"] + ore_table["ot"] + ore_table["sp"] + ore_table["va"],
            "r32": ore_table["ca"] + ore_table["ci"] + ore_table["po"] + ore_table["zi"],
            "r64": ore_table["lo"] + ore_table["mo"] + ore_table["xe"] + ore_table["yt"]
        }

        if row[0] in regions:
            regions[row[0]]["scanned_moons"] += 1

            for key in regions[row[0]]["ore_composition"]:
                regions[row[0]]["ore_composition"][key] += ore_table[key]

            for key in regions[row[0]]["ore_summary"]:
                regions[row[0]]["ore_summary"][key] += ore_summary[key]
        else:
            regions[row[0]] = {
                "region_id": row[0],
                "region": row[1],
                "ore_composition": ore_table,
                "ore_summary": ore_summary,
                "scanned_moons": 1,
                "total_moons": 0
            }

    constellations = {}

    def get_constellations(region_id):
        import common.request_esi

        request_region_url = 'universe/regions/{}/'.format(region_id)
        esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url, method='get')

        if not esi_region_code == 200:
            logger.error("/universe/regions/ API error {0}: {1}"
                         .format(esi_region_code, esi_region_result.get('error', 'N/A')))
            return None

        return esi_region_result["constellations"]

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_constellations, region_id): region_id for region_id in regions}
        for future in as_completed(futures):
            region_id = futures[future]
            result = future.result()

            if result is not None:
                if region_id in constellations:
                    constellations[region_id].extend(result)
                else:
                    constellations[region_id] = result

    systems = {}

    def get_systems(const_id):
        import common.request_esi

        request_const_url = 'universe/constellations/{}/'.format(const_id)
        esi_const_code, esi_const_result = common.request_esi.esi(__name__, request_const_url, method='get')

        if not esi_const_code == 200:
            logger.error("/universe/constellations/ API error {0}: {1}"
                         .format(esi_const_code, esi_const_result.get('error', 'N/A')))
            return None

        return esi_const_result["systems"]

    for region_id in constellations:
        with ThreadPoolExecutor(10) as executor:
            futures = {executor.submit(get_systems, const_id): const_id for const_id in constellations[region_id]}
            for future in as_completed(futures):
                result = future.result()

                if result is not None:
                    if region_id in systems:
                        systems[region_id].extend(result)
                    else:
                        systems[region_id] = result

    moons = {}

    def get_moons(system_id):
        import common.request_esi

        request_system_url = 'universe/systems/{}/'.format(system_id)
        esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

        if not esi_system_code == 200:
            logger.error("/universe/systems/ API error {0}: {1}"
                         .format(esi_system_code, esi_system_result.get('error', 'N/A')))
            return None

        moons = []

        for planet in esi_system_result["planets"]:
            moons.extend(planet.get("moons", []))

        return moons

    for region_id in systems:
        with ThreadPoolExecutor(10) as executor:
            futures = {executor.submit(get_moons, system_id): system_id for system_id in systems[region_id]}
            for future in as_completed(futures):
                result = future.result()

                if result is not None:
                    if region_id in moons:
                        moons[region_id].extend(result)
                    else:
                        moons[region_id] = result

    for region_id in moons:
        regions[region_id]["total_moons"] = len(moons[region_id])

    region_list = []

    for region_id in regions:
        region_list.append(regions[region_id])

    return flask.Response(json.dumps(region_list), status=200, mimetype='application/json')


@blueprint.route('/<int:user_id>/moons/', methods=['POST'])
@verify_user(groups=['triumvirate'])
def moons_post(user_id):
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import MySQLdb as mysql
    import json
    import re

    from common.logger import securitylog
    from ._roman import fromRoman
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger = logging.getLogger(__name__)

    lines = str(flask.request.get_json().get('text', "")).splitlines()

    securitylog(__name__, 'submitted moon scan',
                detail='attempt (lines={})'.format(len(lines)),
                ipaddress=flask.request.headers['X-Real-Ip'],
                charid=user_id)

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")
    regex_win = re.compile("\\t(.*)\\t([0-9]\.[0-9]+)\\t([0-9]+)\\t([0-9]+)\\t([0-9]+)\\t([0-9]+)")

    moons = []

    for i in range(0, len(lines)):
        match = regex_moon.match(lines[i])

        if match:
            moon = {
                'system': match.group(1).strip(),
                'planet': int(fromRoman(match.group(2)+match.group(3))),
                'moon': int(match.group(4)),
                'ore_composition': {},
                'valid': False
            }

            for j in range(1, 5):
                try:
                    match_mineral = regex_win.match(lines[i + 1])
                except IndexError:
                    break

                if not match_mineral:
                    logger.warning('no regex match for line: {0} (if this is a new moon ignore)'.format(lines[i + 1]))
                    break

                moon['valid'] = True

                moon['system_id'] = int(match_mineral.group(4))
                moon['planet_id'] = int(match_mineral.group(5))
                moon['moon_id'] = int(match_mineral.group(6))

                moon['ore_composition'][str(match_mineral.group(1).strip())] = float(match_mineral.group(2))

                i += 1

            moons.append(moon)

    def update_moon(_moon):
        if 'system_id' in _moon:
            import common.request_esi

            # get system details
            request_system_url = 'universe/systems/{}/'.format(_moon['system_id'])
            esi_system_code, esi_system_result = common.request_esi.esi(__name__, request_system_url, method='get')

            if not esi_system_code == 200:
                logger.error("/universe/systems/ API error {0}: {1}"
                             .format(esi_system_code, esi_system_result.get('error', 'N/A')))
                return {}

            constellation_id = esi_system_result['constellation_id']

            # get constellation details
            request_const_url = 'universe/constellations/{}/'.format(constellation_id)
            esi_const_code, esi_const_result = common.request_esi.esi(__name__, request_const_url, method='get')

            if not esi_const_code == 200:
                logger.error("/universe/constellations/ API error {0}: {1}"
                             .format(esi_const_code, esi_const_result.get('error', 'N/A')))
                return {}

            constellation_name = esi_const_result['name']
            region_id = esi_const_result['region_id']

            # get region details
            request_region_url = 'universe/regions/{}/'.format(region_id)
            esi_region_code, esi_region_result = common.request_esi.esi(__name__, request_region_url, method='get')

            if not esi_region_code == 200:
                logger.error("/universe/regions/ API error {0}: {1}"
                             .format(esi_region_code, esi_region_result.get('error', 'N/A')))
                return {}

            region_name = esi_region_result['name']

            # get moon details
            request_moon_url = 'universe/moons/{}/'.format(_moon['moon_id'])
            esi_moon_code, esi_moon_result = common.request_esi.esi(__name__, request_moon_url, method='get')

            if not esi_moon_code == 200:
                logger.error("/universe/moons/ API error {0}: {1}"
                             .format(esi_moon_code, esi_moon_result.get('error', 'N/A')))
                return {}

            moon_position = esi_moon_result['position']

            _moon['const_id'] = constellation_id
            _moon['const'] = constellation_name
            _moon['region_id'] = region_id
            _moon['region'] = region_name
            _moon['position'] = moon_position

        return _moon

    with ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(update_moon, moon): moon for moon in moons}
        for future in as_completed(futures):
            moon = futures[future]
            moon.update(future.result())

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
                                   "(moonId, moonNr,moonPosition , planetId, planetNr, regionId, "
                                   "regionName, constellationId, constellationName, solarSystemId, solarSystemName,"
                                   "oreComposition, scannedBy, scannedByName, scannedDate) VALUES "
                                   "(%s, %s, %s, %s, %s, %s,"
                                   "%s, %s, %s, %s, %s,"
                                   "%s, %s, %s, NOW())",
                                   (moon['moon_id'], moon['moon'], json.dumps(moon["position"]), moon['planet_id'], moon['planet'], moon['region_id'],
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
                                       "(%s, %s, %s, %s, %s, %s,"
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

    securitylog(__name__, 'submitted moon scan',
                detail='success ({0},{1},{2})'.format(new_moons, old_moons, conflicts),
                ipaddress=flask.request.headers['X-Real-Ip'],
                charid=user_id)

    return flask.Response(json.dumps({
        'added': new_moons,
        'duplicates': old_moons,
        'conflicts': conflicts
    }), status=200, mimetype='application/json')


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
