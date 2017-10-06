from ..core2 import blueprint


@blueprint.route('/<int:user_id>/', methods=['GET'])
def user_endpoint(user_id):
    import flask
    import json

    return flask.Response(json.dumps({'user_id': user_id}), status=200, mimetype='application/json')
