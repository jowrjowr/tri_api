import flask as _flask

blueprint = _flask.Blueprint("core2", __name__, url_prefix="/core2")

from .user import user_endpoint


def verify_user(func, groups=None, roles=None):
    from functools import wraps

    @wraps(func)
    def decorated_function(*args, **kwargs):
        import common.ldaphelpers as _ldaphelpers
        import flask
        import logging
        import json

        logger = logging.getLogger(__name__)

        user_id = kwargs.get('user_id')

        code, result = _ldaphelpers.ldap_search(__name__, 'ou=People,dc=triumvirate,dc=rocks',
                                                '(uid={})'.format(user_id), ['authGroup', 'corporationRole'])

        if not code:
            logger.error("unable to fetch ldap information for uid {}".format(user_id))
            return flask.Response(json.dumps({'error': 'ldap error'}), status=500, mimetype='application/json')

        if result is None:
            logger.error("user with uid {} missing".format(user_id))
            return flask.Response(json.dumps({'error': 'user not found'}), status=404, mimetype='application/json')

        (_, user_data), = result.items()

        if groups is not None:
            if all(isinstance(l, list) for l in groups):
                any_valid = False

                for l in groups:
                    if all(required_group in user_data['authGroup'] for required_group in l):
                        any_valid = True

                if not any_valid:
                    return flask.Response(json.dumps({'error': 'missing necessary auth groups'}), status=403,
                                          mimetype='application/json')
            elif all(isinstance(s, str) for s in groups):
                if not any(required_group in user_data['authGroup'] for required_group in groups):
                    return flask.Response(json.dumps({'error': 'missing necessary auth groups'}), status=403,
                                          mimetype='application/json')
            else:
                logger.error("verify_user failed as groups are not a list of strings or a list of string lists")
                return flask.Response(json.dumps({'error': 'verify_user failed'}),
                                      status=500, mimetype='application/json')
        if roles is not None:
            if all(isinstance(l, list) for l in roles):
                any_valid = False

                for l in roles:
                    if all(required_role in user_data['corporationRole'] for required_role in l):
                        any_valid = True

                if not any_valid:
                    return flask.Response(json.dumps({'error': 'missing necessary roles'}), status=403,
                                          mimetype='application/json')
            elif all(isinstance(s, str) for s in roles):
                if not any(required_role in user_data['corporationRole'] for required_role in roles):
                    return flask.Response(json.dumps({'error': 'missing necessary roles'}), status=403,
                                          mimetype='application/json')
            else:
                logger.error("verify_user failed as roles are not a list of strings or a list of string lists")
                return flask.Response(json.dumps({'error': 'verify_user failed'}),
                                      status=500, mimetype='application/json')
    return decorated_function
