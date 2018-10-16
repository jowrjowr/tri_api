from flask import request
from tri_api import app

@app.route('/core/group/<group>/broadcast', methods=[ 'POST' ])
def core_group_broadcast(group):

    from flask import request, json, Response
    import common.logger as _logger
    from tri_core.common.broadcast import broadcast

    ipaddress = request.args.get('log_ip')
    charid = request.args.get('charid')

    if ipaddress is None:
        ipaddress = request.headers['X-Real-Ip']

    message = request.get_data()
    message = message.decode('utf-8')

    # spew at a group
    if request.method == 'POST':
        _logger.securitylog(__name__, 'broadcast', detail='group {0}'.format(group), ipaddress=ipaddress, charid=charid)
        broadcast(message, group=group)
        return Response({}, status=200, mimetype='application/json')

@app.route('/core/corp/<int:corpid>/broadcast', methods=[ 'POST' ])
def core_corp_broadcast(corpid):

    from flask import request, json, Response
    import common.logger as _logger
    from tri_core.common.broadcast import broadcast
    ipaddress = 'automated'
    message = request.get_data()
    message = message.decode('utf-8')

    # spew at a specific corpid
    if request.method == 'POST':
        _logger.securitylog(__name__, 'broadcast', detail='corpid {0}'.format(corpid), ipaddress=ipaddress)
        broadcast(message, corpid=corpid)
        return Response({}, status=200, mimetype='application/json')


