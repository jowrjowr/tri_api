from flask import request
from tri_api import app

@app.route('/core/esi/<version>/<path:url>', methods=['GET', 'POST'])
def core_esi_passthrough(version, url):

    from flask import Flask, request, url_for, json, Response
    import common.request_esi
    import common.logger as _logger
    import json
    import urllib

    # a wrapper around standard ESI requests for things like php core

    if 'charid' not in request.args:
        _logger.log('[' + __name__ + '] no charid parameter', _logger.LogLevel.WARNING)
        js = json.dumps({ 'error': 'need an charid to authenticate using'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    try:
        charid = int(request.args['charid'])
    except ValueError:
        _logger.log('[' + __name__ + '] invalid charid: "{0}"'.format(request.args['charid']), _logger.LogLevel.WARNING)
        js = json.dumps({ 'error': 'charid parameter must be integer'})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    # make a copy of the parameters

    parameters = dict()
    for key in request.args:
        parameters[key] = request.args[key]

    charid = parameters['charid']
    del(parameters['charid'])

    _logger.log('[' + __name__ + '] esi passthrough request for charid {0}: {1}'.format(request.args['charid'], url), _logger.LogLevel.DEBUG)

    parameterstring = urllib.parse.urlencode(parameters)

    # we're going to just pass the request through with the access token attached

    if len(parameters) > 0:
        esi_url = url + '?' + parameterstring
    else:
        esi_url = url

    if request.method == 'GET':
        code, result = common.request_esi.esi(__name__, esi_url, method='get', version=version, charid=charid)
    if request.method == 'POST':
        code, result = common.request_esi.esi(__name__, esi_url, method='post', version=version, charid=charid, data=request.get_data())

    resp = Response(json.dumps(result), status=code, mimetype='application/json')
    return resp
