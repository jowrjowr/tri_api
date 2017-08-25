from flask import request, json, request, Response
from tri_api import app

import ts3
import common.ldaphelpers as _ldaphelpers
import common.logger as _logger
import common.credentials.ts3 as _ts3
import common.request_esi

from tri_core.common.tsgroups import teamspeak_groups

@app.route('/core/teamspeak/<charid>', methods=['DELETE', 'GET', 'POST'])
def core_teamspeak(charid):

    ipaddress = request.headers['X-Real-Ip']
    # remove the TS information from a given char
    if request.method == 'DELETE':
        _logger.securitylog(__name__, 'teamspeak identity delete', charid=charid, ipaddress=ipaddress)
        return teamspeak_DELETE(charid)

    # get current TS info for a charid
    if request.method == 'GET':
        return teamspeak_GET(charid)

    # update/make new teamspeak identity
    if request.method == 'POST':
        _logger.securitylog(__name__, 'teamspeak identity creation', charid=charid, ipaddress=ipaddress)
        return teamspeak_POST(charid)

def teamspeak_POST(charid):

    # make a new ts3 identity

    try:
        # Note, that the client will wait for the response and raise a
        # **TS3QueryError** if the error id of the response is not 0.
        ts3conn = ts3.query.TS3Connection(_ts3.TS_HOST)
        ts3conn.login(
            client_login_name=_ts3.TS_USER,
            client_login_password=_ts3.TS_PASSWORD
        )
    except ts3.query.TS3QueryError as err:
        msg = 'unable to connect to TS3: {0}'.format(err.resp.error["msg"])
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg })
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    ts3conn.use(sid=_ts3.TS_SERVER_ID)

    # snag existing ts info. this will matter later.

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist= ['teamspeakuid', 'teamspeakdbid', 'characterName', 'authGroup', 'uid', 'alliance', 'corporation']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap users: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        # this should NEVER happen
        msg = 'charid {0} not in ldap'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=404, mimetype='application/json')
        return resp

    (dn, info), = result.items()

    groups = info['authGroup']
    charname = info['characterName']

    # check if a duplicate

    ts_dbid = info.get('teamspeakdbid')
    ts_uid = info.get('teamspeakuid')

    if ts_dbid != None or ts_dbid != None:
        # we have a live account. nuke it and try again.
        msg = 'existing teamspeak client. dbid: {0} uid: {1}'.format(ts_dbid, ts_uid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=400, mimetype='application/json')
        return resp

    # snag the client list

    try:
        resp = ts3conn.clientlist()
        clients = resp.parsed
    except ts3.query.TS3QueryError as err:
        msg = 'ts3 error: "{0}"'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    # loop through the client list to find the matching client

    for client in clients:
        clid = client['clid']
        cldbid = client['client_database_id']
        client_username = client['client_nickname']

        if client_username == charname:
            # found a match.
            ts_dbid = client['client_database_id']
            ts_uid = client['clid']

    if ts_dbid == None or ts_uid == None:

        msg = 'unable to locate matching teamspeak user for {}'.format(charname)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=404, mimetype='application/json')
        return resp

    # we want the unique identifier
    try:
        resp = ts3conn.clientinfo(clid=ts_uid)
        result = resp.parsed
    except ts3.query.TS3QueryError as err:
        msg = 'ts3 error: "{0}"'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    ts_uid = result[0]['client_unique_identifier']

    # matching account found. store in ldap.

    _ldaphelpers.update_singlevalue(dn, 'teamspeakdbid', ts_dbid)
    _ldaphelpers.update_singlevalue(dn, 'teamspeakuid', ts_uid)

    # setup groups for the ts user

    code, result = teamspeak_groups(charid)

    if code == False:
        msg = 'unable to setup teamspeak groups for {0}: {1}'.format(charname, result)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        return Response(js, status=500, mimetype='application/json')
    else:
        return Response({}, status=200, mimetype='application/json')

def teamspeak_GET(charid):

    # fetch the teamspeak information from a given charid

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist= ['teamspeakuid', 'teamspeakdbid', 'characterName', 'authGroup', 'uid', 'alliance', 'corporation']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap users: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        # this should NEVER happen
        msg = 'charid {0} not in ldap'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=404, mimetype='application/json')
        return resp

    (dn, info), = result.items()

    result = dict()
    result['teamspeakdbid'] = info.get('teamspeakdbid')
    result['teamspeakuid'] = info.get('teamspeakuid')

    js = json.dumps(result)
    resp = Response(js, status=200, mimetype='application/json')
    return resp

def teamspeak_DELETE(charid):


    # remove the teamspeak information the character's ldap

    # connections

    try:
        # Note, that the client will wait for the response and raise a
        # **TS3QueryError** if the error id of the response is not 0.
        ts3conn = ts3.query.TS3Connection(_ts3.TS_HOST)
        ts3conn.login(
            client_login_name=_ts3.TS_USER,
            client_login_password=_ts3.TS_PASSWORD
        )
    except ts3.query.TS3QueryError as err:
        msg = 'unable to connect to TS3: {0}'.format(err.resp.error["msg"])
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    ts3conn.use(sid=_ts3.TS_SERVER_ID)

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist= ['teamspeakuid', 'teamspeakdbid', 'characterName', 'authGroup', 'uid', 'alliance', 'corporation']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap users: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    if result == None:
        # this should NEVER happen
        msg = 'charid {0} not in ldap'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=404, mimetype='application/json')
        return resp

    (dn, info), = result.items()

    ts_dbid = info.get('teamspeakdbid')
    ts_uid = info.get('teamspeakuid')

    if ts_dbid == None:
        # shouldn't happen!
        msg = 'character {0} has no teamspeak to purge'.format(charid)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
        js = json.dumps({ 'error': msg })
        resp = Response(js, status=404, mimetype='application/json')
        return resp

    # purge from ts3


    # have to kick before purging, but to do that the client id (not the dbid) has to be located
    # snag the client list

    try:
        resp = ts3conn.clientlist()
        clients = resp.parsed
    except ts3.query.TS3QueryError as err:
        msg = 'ts3 error: "{0}"'.format(err)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    # loop through the client list to find the matching client

    ts_uid = None

    for client in clients:
        clid = client['clid']

        if ts_dbid == client['client_database_id']:
            # found a match.
            ts_uid = client['clid']

    if not ts_uid == None:
        try:
            reason = 'kicking to purge old TS identity, reregister now'
            resp = ts3conn.clientkick(reasonid=5, reasonmsg=reason, clid=ts_uid)
        except ts3.query.TS3QueryError as err:
            msg = 'unable to kick client dbid {0}, client id {1} from teamspeak'.format(ts_dbid, ts_uid, err)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            js = json.dumps({ 'error': msg})
            resp = Response(js, status=500, mimetype='application/json')
            return resp

    try:
        resp = ts3conn.clientdbdelete(cldbid=ts_dbid)
    except ts3.query.TS3QueryError as err:
        msg = 'unable to remove client dbid {0} for charid {1}: "{2}"'.format(ts_dbid, charid, err)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    # purge from ldap

    _ldaphelpers.update_singlevalue(dn, 'teamspeakdbid', None)
    _ldaphelpers.update_singlevalue(dn, 'teamspeakuid', None)

    # success if we made it this far

    resp = Response('{}', status=200, mimetype='application/json')
    return resp
