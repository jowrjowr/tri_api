from ..core2 import blueprint
from .decorators import verify_user


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

    logger = logging.getLogger(__name__)

    lines = str(flask.request.get_data()).split('\\n')

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")
    regex_mineral = re.compile("\s*(.*)\s+([0-9]\.[0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)")

    moons = []

    for i in range(0, len(lines)):
        match = regex_moon.match(lines[i])

        if match:
            moon = {
                'system': match.group(1),
                'planet': match.group(3),
                'moon': match.group(4),
                'minerals': []
            }

            for j in range(1, 5):
                match_mineral = regex_mineral.match(lines[i+1])

                if not match_mineral:
                    break

                moon['system_id'] = match_mineral.group(4)
                moon['planet_id'] = match_mineral.group(5)
                moon['moon_id'] = match_mineral.group(6)

                moon['minerals'].append({
                    'product': match_mineral.group(1),
                    'quantity': match_mineral.group(2),
                    'ore_type': match_mineral.group(3),
                })

                i += 1

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

    try:
        for moon in moons:
            cursor.execute("INSERT INTO MoonScans "
                           "(moonId, moonNr, planetId, planetNr, solarSystemId, "
                           "solarSystemName, oreComposition, scannedBy, scannedDate) VALUES "
                           "(%i, %i, %i, %i, %i,"
                           "%s, %s, %i, NOW())",
                           (moon['moon_id'], moon['moon'], moon['planet_id'], moon['planet'], moon['system_id'],
                            moon['system'], json.dumps(moon['minerals']), user_id))
            cursor.execute()
    except mysql.Error as error:
        sql_conn.rollback()
        logger.error('mysql error: {0}'.format(error))
        return flask.Response(json.dumps({'error': str(error)}), status=500, mimetype='application/json')
    finally:
        sql_conn.close()

    return flask.Response(json.dumps(moons), status=200, mimetype='application/json')
