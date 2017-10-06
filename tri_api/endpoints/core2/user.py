from ..core2 import blueprint


@blueprint.route('/<int:user_id>/', methods=['GET'])
def user_endpoint(user_id):
    import flask

    return flask.Response({'user_id': user_id}, status=200, mimetype='application/json')
