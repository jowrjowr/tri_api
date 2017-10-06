from ..core2 import blueprint


def user_access_roles(groups, roles):
    access = {
        'routes': [],
        'services': ['forum'],
        'tools': []
    }

    if 'banned' in groups:
        return dict()

    # teamspeak
    if 'triumvirate' in groups or 'vanguardBlue' in groups:
        access['services'].append('teamspeak')

    # discord & jabber
    if 'triumvirate' in groups:
        access['services'].append('discord')
        access['services'].append('jabber')

    # fleet stuff
    if 'triumvirate' in groups or 'vanguardBlue' in groups:
        access['routes'].append('opsboard')

    # tri only
    if 'triumvirate' in groups:
        access['routes'].append('srp')

    # broadcast
    if 'Director' in roles or 'Personnel_Manager' in roles \
        or 'skyteam' in groups or 'skirmishfc' in groups or 'administration' in groups:
        access['tools'].append('broadcast')

    # blacklist
    if 'Director' in roles or 'Personnel_Manager' in roles:
        access['tools'].append('blacklist')

    #  corp tools
    if 'command' in groups or 'administration' in roles:
        access['tools'].append('corp_audit')
        access['tools'].append('corp_structures')

    #  alliance tools
    if 'command' in groups or 'board' in groups:
        access['tools'].append('alliance_audit')
        access['tools'].append('alliance_structures')

    return access


@blueprint.route('/<int:user_id>/', methods=['GET'])
def user_endpoint(user_id):
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

    access_roles = user_access_roles(user['authGroup'], user['corporationRole'])

    return flask.Response(json.dumps(
        {
            'character_id': user['uid'],
            'character_name': user['corporationName'],
            'corporation_id': user['corporation'],
            'corporation_name': user['corporationName'],
            'alliance_id': user['alliance'],
            'alliance_name': user['allianceName'],
            'groups': user['authGroup'],
            'access': access_roles
        }
    ), status=200, mimetype='application/json')
