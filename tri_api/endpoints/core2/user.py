from ..core2 import blueprint
from .decorators import verify_user


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

    # resolve access

    access = {
        'resources': [],
        'services': ['forums'],
        'corp_tools': [],
        'alliance_tools': []
    }

    if 'triumvirate' in user['authGroup']:
        # basic services
        access['services'].extend(['jabber', 'teamspeak', 'discord'])

        # basic resources
        access['resources'].extend(['ops', 'doctrines', 'srp', 'jb_map'])

        access['alliance_tools'].extend(['timerboard_submit'])

        if 'bannedBroadcast' not in user['authGroup']:
            access['services'].append('broadcast')

        # supers stuff
        if 'trisupers' in user['authGroup']:
            access['resources'].append('supers')

        # timer board
        if 'skyteam' in user['authGroup']:
            access['resources'].append('timerboard_view')

        # blacklist
        if 'Director' in user['corporationRole'] or 'Personnel_Manager' in user['corporationRole']\
                or 'board' in 'skyteam' in user['authGroup']:
            access['resources'].append('blacklist')

        # moon probing
        if 'Director' in user['corporationRole'] or 'administration' in user['authGroup']\
                or 'triprobers' in user['authGroup']:
            access['resources'].append('moons_submit')

        # corp leadership
        if 'Director' in user['corporationRole'] or 'administration' in user['authGroup']:
            access['corp_tools'].append('audit')
            access['corp_tools'].append('structures')

        # alliance leadership
        if 'board' in user['authGroup']:
            access['alliance_tools'].append('audit')
            access['alliance_tools'].append('structures')
            access['resources'].append('moons_view')

    return flask.Response(json.dumps(
        {
            'character_id': user['uid'],
            'character_name': user['corporationName'],
            'corporation_id': user['corporation'],
            'corporation_name': user['corporationName'],
            'alliance_id': user['alliance'],
            'alliance_name': user['allianceName'],
            'groups': user['authGroup'],
            'roles': user['corporationRole'],
            'access': access
        }
    ), status=200, mimetype='application/json')
