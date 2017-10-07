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

    data = str(flask.request.get_data())

    regex = re.compile("(.+) - Moon ^\d+$")

    result = regex.search(data)

    return flask.Response(result.group(1))
