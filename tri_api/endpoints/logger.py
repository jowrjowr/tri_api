from tri_api import app
from flask import request, Response
import common.logger as _logger

@app.route('/core/logger/', methods=['POST'])
def core_logger():

    # an endpoint wrapper to drop stuff into the security log
    # this is deliberately very thin

    action = request.values.get('action')
    charid = request.values.get('charid')
    charname = request.values.get('charname')
    ipaddress = request.values.get('ipaddress')
    date = request.values.get('date')
    detail = request.values.get('detail')

    # we do not care about the return code because this failing should not impact the thing that is using it. not yet.

    _logger.securitylog(__name__, action, charid=charid, charname=charname, ipaddress=ipaddress, date=date, detail=detail)

    return Response({}, status=200, mimetype='application/json')
