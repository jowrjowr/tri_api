from ..core2 import blueprint
from .decorators import verify_user


@blueprint.route('/<int:user_id>/moons/', methods=['POST'])
@verify_user(groups=['board', 'administation', 'triprobers'])
def moons_post(user_id):
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import json
    import re

    logger = logging.getLogger(__name__)

    lines = str(flask.request.get_data()).split('\\n')

    regex_moon = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")
    regex_mineral = re.compile("\t(.*)\t([0-9]\.[0-9]+)\t([0-9]+)\t([0-9]+)\t([0-9]+)\t([0-9]+)")

    moons = []

    for i in range(0, len(lines)):
        match = regex_moon.match(lines[i])

        if match:
            moon = {
                'system_name': match.group(1),
                'planet_name': match.group(2),
                'moon_name': match.group(3),
                'minerals': []
            }

            for j in range(0, 4):
                match_mineral = regex_mineral.match(lines[i+j])

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

    return flask.Response(json.dumps(moons), status=200, mimetype='application/json')
