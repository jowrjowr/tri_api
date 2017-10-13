from ..core2 import blueprint


@blueprint.route('/<int:user_id>/', methods=['GET'])
def user_get(user_id):
    import common.ldaphelpers as _ldaphelpers
    import flask
    import logging
    import json

    logger = logging.getLogger(__name__)

    code, result = _ldaphelpers.ldap_search(__name__, 'ou=People,dc=triumvirate,dc=rocks',
                                            '(uid={})'.format(user_id),
                                            ['uid', 'characterName',
                                             'corporation', 'corporationName',
                                             'alliance', 'allianceName',
                                             'authGroup', 'corporationRole'])

    if not code:
        logger.error("unable to fetch ldap information for uid {}".format(user_id))
        return flask.Response(json.dumps({'error': 'ldap error'}), status=500, mimetype='application/json')

    if result is None:
        logger.error("user with uid {} missing".format(user_id))
        return flask.Response(json.dumps({'error': 'user not found'}), status=404, mimetype='application/json')

    (_, user), = result.items()

    return flask.Response(json.dumps(
        {
            'character_id': user['uid'],
            'character_name': user['corporationName'],
            'corporation_id': user['corporation'],
            'corporation_name': user['corporationName'],
            'alliance_id': user['alliance'],
            'alliance_name': user['allianceName'],
            'groups': user['authGroup'],
            'roles': user['corporationRole']
        }
    ), status=200, mimetype='application/json')
