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

    regex_header = re.compile("(.*) (XC|XL|L?X{0,3})(IX|IV|V?I{0,3}) - Moon ([0-9]{1,3})")
    regex_lines = re.compile("\t(.*)\t([0-9]\.[0-9]+)\t([0-9]+)\t([0-9]+)\t([0-9]+)\t([0-9]+)")

    return flask.Response(regex_header.match(lines[1]).group(1))
