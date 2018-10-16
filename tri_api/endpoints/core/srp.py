from tri_api import app
from flask import Response, request
import json
import re
import requests
import time
import common.logger as _logger
import common.database as _database
import common.esihelpers as _esihelpers
import common.ldaphelpers as _ldaphelpers
import MySQLdb as mysql
import common.request_esi as _esi
from common.logger import getlogger_new as getlogger
from common.logger import securitylog_new as securitylog

@app.route('/core/srp/requests/<int:char_id>/', methods=['GET'])
def core_srp_requests(char_id):

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        logger.error(msg)
        js = json.dumps({'error': str(err)})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    cursor = sql_conn.cursor()

    query = 'SELECT RequestTime, LossTime, charName, zkbLink, ShipType, estPayout FROM SRP WHERE RequestedByCharID = {0} AND srpStatus = 0'.format(char_id)
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        js = json.dumps({'error': str(err)})
        resp = Response(js, status=500, mimetype='application/json')
        return resp
    finally:
        cursor.close()

    requests = []

    for row in rows:
        requests.append({
            'date': row[0].isoformat(),
            'km_date': row[1].isoformat(),
            'character_name': row[2],
            'zkb': row[3],
            'ship': row[4],
            'payout': row[5]
        })

    return Response(json.dumps(requests), status=200, mimetype='application/json')


@app.route('/core/srp/requests/<int:charid>/past/', methods=['POST'])
def core_srp_requests_past(charid):

    logger = getlogger('core.srp.post')

    ipaddress = request.args.get('log_ip')
    if ipaddress is None:
        ipaddress = request.headers['X-Real-Ip']

    securitylog('SRP post', ipaddress=ipaddress, charid=charid)

    kill_url = request.form['url']
    fleetfc = request.form['fleetfc']
    notes = request.form['notes']

    # only people in tri can get SRP

    affiliations = _esihelpers.esi_affiliations(charid)

    if affiliations['allianceid'] != 933731581:
        response = { 'error': 'not eligible for SRP' }
        return Response(json.dumps(response), status=401, mimetype='application/json')

    # use regex to get the zkill kill ID

    pattern = re.compile('(.*)zkillboard.com/kill/(\d+)(.*)')
    match = re.match(pattern, kill_url)
    if match:
        killid = match.group(2)
    else:
        response = { 'error': 'unable to parse zkill url: {0}'.format(kill_url) }
        return Response(json.dumps(response), status=400, mimetype='application/json')

    # fetch zkill data

    request_url = 'killID/{}/'.format(killid)
    code, result = _esi.esi(__name__, request_url, base='zkill')

    try:
        if result.get('error'):
            msg = 'zkill error {0}: {1}'.format(request_url, result['error'])
            logger.error(msg)
            response = { 'error': msg }
            return Response(json.dumps(response), status=400, mimetype='application/json')
    except Exception as e:
        # fucked up zkill api spews different datatypes and doesn't use http return codes right
        pass

    killhash = result[0]['zkb']['hash']
    value = result[0]['zkb']['totalValue']

    # fetch actual kill data from ESI

    request_url = 'killmails/{0}/{1}/'.format(killid, killhash)
    code, result = _esi.esi(__name__, request_url, version='v1')

    if code != 200:
        msg = 'ESI error {0}: {1}'.format(request_url, result)
        response = { 'error': msg }
        logger.error(msg)
        return Response(json.dumps(response), status=500, mimetype='application/json')


    killtime = result['killmail_time']
    victim = result['victim']
    shipid = result['victim']['ship_type_id']
    victimid = result['victim']['character_id']
    victim = _esihelpers.esi_affiliations(victimid)

    request_url = 'universe/types/{}/'.format(shipid)
    code, result = _esi.esi(__name__, request_url)

    if code != 200:
        msg = 'ESI error {0}: {1}'.format(request_url, result)
        response = { 'error': msg }
        logger.error(msg)
        return Response(json.dumps(response), status=500, mimetype='application/json')

    shipname = result['name']

    killtime = killtime.replace('T', ' ')
    killtime = killtime.replace('Z', '')

    # start doing db checks

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)

    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        logger.error(msg)
        js = json.dumps({'error': msg })
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    cursor = sql_conn.cursor()

    # check that there is no duplicate killmail

    query = 'SELECT killID from SRP where killID=%s'
    try:
        rowcount = cursor.execute(query, (killid,))
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        logger.error(msg)
        js = json.dumps({'error': msg })
        cursor.close()
        return Response(js, status=500, mimetype='application/json')

    if rowcount > 0:
        msg = 'kill ID {0} already submitted for SRP'.format(killid)
        js = json.dumps({'error': msg })
        cursor.close()
        return Response(js, status=400, mimetype='application/json')

    # fetch estimated payout
    query = 'SELECT value FROM CalcSRP WHERE shipTypeID=%s'
    try:
        rowcount = cursor.execute(query, (shipid,))
        rows = cursor.fetchall()
    except mysql.Error as err:
        msg = 'mysql error: {0}'.format(err)
        logger.error(msg)
        js = json.dumps({'error': msg })
        cursor.close()
        return Response(js, status=500, mimetype='application/json')

    if rowcount == 0:
        msg = 'ship type {0} not eligible for SRP'.format(shipname)
        js = json.dumps({'error': msg })
        cursor.close()
        return Response(js, status=400, mimetype='application/json')

    payout, = rows
    payout = payout[0]

    # map the charid to a charnme for payments

    paychar = _esihelpers.esi_affiliations(charid)
    paychar = paychar['charname']

    # insert data into SRP table

    query = 'INSERT into SRP (RequestTime, RequestedByCharID, LossTime, Shiptype, shipTypeID, charID, '
    query += 'charName, zkbLink, killID, srpStatus, payChar, fleetFC, estPayout, obs)'
    query += ' VALUES (FROM_UNIXTIME(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
    try:
        result = cursor.execute(query, (
            time.time(), charid, killtime, shipname, shipid, victimid,
            victim['charname'], kill_url, killid, 0, paychar, fleetfc, payout, notes
            )
        )
    except mysql.Error as err:
        msg = 'mysql error inserting SRP: {0}'.format(err)
        logger.error(msg)
        js = json.dumps({'error': msg })
        cursor.close()
        return Response(js, status=500, mimetype='application/json')

    sql_conn.commit()
    cursor.close()

    return Response({}, status=200, mimetype='application/json')
