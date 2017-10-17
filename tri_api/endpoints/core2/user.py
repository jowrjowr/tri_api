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
        'tools': []
    }

    if 'triumvirate' in user['authGroup']:
        # basic services
        access['services'].extend(['jabber', 'teamspeak', 'discord'])

        # basic resources
        access['resources'].extend(['ops', 'doctrines', 'srp', 'jb_map'])

        access['tools'].extend(['timerboard_submit'])

        if 'bannedBroadcast' not in user['authGroup']:
            access['tools'].append('broadcast')

        # supers stuff
        if 'trisupers' in user['authGroup']:
            access['resources'].append('supers')

        # timer board
        if 'skyteam' in user['authGroup']:
            access['tools'].append('timerboard_view')

        # blacklist
        if 'Director' in user['corporationRole'] or 'Personnel_Manager' in user['corporationRole']\
                or 'board' in 'skyteam' in user['authGroup']:
            access['tools'].append('blacklist_submit')
            access['tools'].append('blacklist_view')

        # moon probing
        if 'Director' in user['corporationRole'] or 'administration' in user['authGroup']\
                or 'triprobers' in user['authGroup']:
            access['tools'].append('moons_submit')

        # corp leadership
        if 'Director' in user['corporationRole'] or 'administration' in user['authGroup']:
            access['tools'].append('corp_audit')
            access['tools'].append('corp_structures')

        # alliance leadership
        if 'Director' in user['corporationRole'] or 'administration' in user['authGroup']:
            access['tools'].append('alliance_audit')
            access['tools'].append('alliance_structures')
            access['tools'].append('moons_view')

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
