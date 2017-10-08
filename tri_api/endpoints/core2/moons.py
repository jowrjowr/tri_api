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

    from .roman import fromRoman

    logger = logging.getLogger(__name__)

    lines = str(flask.request.get_data()).replace('\\r\\n', '\\n').split('\\n').decode("utf-8")

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")
    regex_lin = re.compile("\s*(.*)\s+([0-9]\.[0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)")
    regex_win = re.compile("\\t(.*)\\t([0-9]\.[0-9]+)\\t([0-9]+)\\t([0-9]+)\\t([0-9]+)\\t([0-9]+)")

    moons = []

    for i in range(0, len(lines)):
        match = regex_moon.match(lines[i])

        if match:
            moon = {
                'system': match.group(1).strip(),
                'planet': int(fromRoman(match.group(3))),
                'moon': int(match.group(4)),
                'minerals': [],
                'valid': False
            }

            for j in range(1, 5):
                match_mineral = regex_win.match(lines[i + 1])

                if not match_mineral:
                    print("REGEX NOT MATCHED: {0}".format(lines[i + 1]))
                    match_mineral = regex_lin.match(lines[i + 1])

                    if not match_mineral:
                        break

                moon['valid'] = True;

                moon['system_id'] = int(match_mineral.group(4))
                moon['planet_id'] = int(match_mineral.group(5))
                moon['moon_id'] = int(match_mineral.group(6))

                moon['minerals'].append({
                    'product': match_mineral.group(1).strip(),
                    'quantity': float(match_mineral.group(2)),
                    'ore_type': int(match_mineral.group(3)),
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
            if moon['valid']:
                cursor.execute("INSERT INTO MoonScans "
                               "(moonId, moonNr, planetId, planetNr, solarSystemId, "
                               "solarSystemName, oreComposition, scannedBy, scannedDate) VALUES "
                               "(%s, %s, %s, %s, %s,"
                               "%s, %s, %s, NOW())",
                               (moon['moon_id'], moon['moon'], moon['planet_id'], moon['planet'], moon['system_id'],
                                moon['system'], json.dumps(moon['minerals']), int(user_id)))
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

    return flask.Response(json.dumps({}), status=200, mimetype='application/json')
