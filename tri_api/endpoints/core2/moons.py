from ..core2 import blueprint, verify_user


@blueprint.route('/<int:user_id>/moons/', methods=['POST'])
@verify_user(['board', 'administation', 'triprobers'])
def moons_post(user_id):
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import json

    logger = logging.getLogger(__name__)

    return flask.Response(json.dumps({}), status=200, mimetype='application/json')
