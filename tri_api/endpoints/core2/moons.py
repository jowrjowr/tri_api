from ..core2 import blueprint
from .decorators import verify_user


class Moon:
    moon_id = None
    moon_name = None

    planet_id = None

    solar_syste_id = None

    composition = dict()

    scanned_by = None
    scanned_when = None


@blueprint.route('/<int:user_id>/moons/', methods=['POST'])
@verify_user(roles=['board', 'administation', 'triprobers'])
def moons_post(user_id):
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import json
    import re

    logger = logging.getLogger(__name__)

    data = flask.request.data.strip()

    if re.match("^[A-Za-z0-9_-]*$", data):
        lines = data.splitlines()

        regex = re.findall("^(M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})|[IDCXMLV])$")

        return str(regex)
    else:
        return flask.Response(json.dumps({'error': 'illegal characters'}), status=400, mimetype='application/json')
