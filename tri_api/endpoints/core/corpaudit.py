from tri_api import app
from flask import request, Response
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.check_role import check_role
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import common.logger as _logger
import common.request_esi
import json
import time

from common.logger import getlogger_new as getlogger
from common.logger import securitylog_new as securitylog

@app.route('/core/corpaudit/<charid>', methods=[ 'GET' ])
def core_corpaudit(charid):


    # do a corp level audit of who has services

    ipaddress = request.headers['X-Real-Ip']
    log_charid = request.args.get('log_charid')

    logger = getlogger('core.corpaudit')
    securitylog('corp audit information request', ipaddress=ipaddress, charid=log_charid)

    try:
        charid = int(charid)
    except ValueError:
        msg = 'charid parameters must be integer: {0}'.format(charid)
        logger.warning(msg)
        js = json.dumps({ 'error': msg})
        resp = Response(js, status=401, mimetype='application/json')
        return resp

    corporation_id_list = []
    character_id_list = []

    dn = 'ou=People,dc=triumvirate,dc=rocks'

    code, char_result = _ldaphelpers.ldap_search(__name__, dn, '(&(|(uid={0})(altOf={0}))(esiAccessToken=*))'
                                                 .format(charid), ['uid', 'corporation', 'corporationName', 'characterName'])

    if code == False:
        error = 'failed to fetch characters for {0}: ({1}) {2}'.format(charid, code, char_result)
        logger.error(error)
        js = json.dumps({'error': error})
        resp = Response(js, status=500, mimetype='application/json')
        return resp

    for cn in char_result:
        data = char_result[cn]
        allowed_roles = ['Director', 'Personnel_Manager']
        roles = check_role(data['uid'], allowed_roles)

        if not roles:
            msg = "character {0} has insufficient roles for {1}".format(data['characterName'], data['corporationName'])
            logger.info(msg)
            continue

        msg = 'character {0} has sufficient roles to view corp auditing information'.format(cn)
        logger.debug(msg)

        if data['corporation'] not in corporation_id_list:
            request_url = 'corporations/{0}/members/'.format(data['corporation'])
            code, result = common.request_esi.esi(__name__, request_url, method='get', charid=data['uid'], version='v3')

            if not code == 200:
                # something broke severely
                msg = 'corporations API error {0}: {1}'.format(code, result)
                logger.error(msg)
                result = {'code': code, 'error': msg}
                return code, result
            character_id_list = result
            corporation_id_list.append(data['corporation'])

    # start constructing which member has what
    users = dict()
    with ThreadPoolExecutor(25) as executor:
        futures = { executor.submit(fetch_chardetails, user): user for user in character_id_list }
        for future in as_completed(futures):
            #charid = futures[future]['character_id']
            data = future.result()

            if data is not None:
                users[data['charname']] = data
    js = json.dumps(users)
    resp = Response(js, status=200, mimetype='application/json')
    return resp

def fetch_chardetails(charid):

    chardetails = dict()

    logger = getlogger('core.corpaudit.chardetails.{0}'.format(charid))

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(uid={})'.format(charid)
    attrlist=['characterName', 'authGroup', 'teamspeakdbid', 'esiAccessToken', 'altOf', 'corporation', 'lastKill', 'lastKillTime','corporationName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if result is None or not code:
        # no result? simple response.
        chardetails['location'] = 'Unknown'
        chardetails['corporation'] = 'Unknown'
        chardetails['online'] = 'Unknown'
        chardetails['last_online'] = 'Unknown'
        chardetails['token_status'] = False
        chardetails['teamspeak_status'] = False
        chardetails['isalt'] = 'Unknown'
        chardetails['lastKill'] = None
        chardetails['lastKillTime'] = None
        chardetails['altof'] = None

        # fetch affiliations

        affiliations = _esihelpers.esi_affiliations(charid)

        chardetails['corporation'] = affiliations.get('corpname')
        chardetails['charname'] = affiliations.get('charname')

    else:
        try:
            (dn, info), = result.items()
        except ValueError:
            print("error: {}".format(charid))

        chardetails['charname'] = info['characterName']

        # convert last kill time into human readable

        try:
            chardetails['lastKill'] = info['lastKill']
        except Exception as e:
            chardetails['lastKill'] = None

        try:
            killtime = int(info['lastKillTime'])
            killtime = time.strftime("%Y/%m/%d, %H:%M:%S", time.localtime(killtime))
            chardetails['lastKillTime'] = killtime
        except Exception as e:
            chardetails['lastKillTime'] = None

        corp_id = info['corporation']

        if corp_id is None:
            print("error: {} no corp".format(charid))

        chardetails['corporation'] = info['corporationName']

        # does the char have a token?

        try:
            detail = info['esiAccessToken']
            if len(detail) > 0:
                chardetails['token_status'] = True
            else:
                chardetails['token_status'] = False
        except Exception as e:
            chardetails['token_status'] = False

        # teamspeak registration?
        try:
            detail = info['teamspeakdbid']
            if len(detail) > 0:
                chardetails['teamspeak_status'] = True
            else:
                chardetails['teamspeak_status'] = False
        except Exception as e:
            chardetails['teamspeak_status'] = False

        # is this an alt?

        # cast the altof detail to something useful

        try:
            detail = info['altOf']
        except Exception as e:
            detail = None

        # str(None) == False
        if str(detail).isdigit():
            chardetails['isalt'] = True
            request_url = 'characters/{0}/'.format(detail)
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if not code == 200:
                msg = '/characters/{0}/ API error {1}: {2}'.format(detail, code, result)
                logger.warning(msg)
            try:
                chardetails['altof'] = result['name']
            except KeyError as error:
                msg = 'User does not exist: {0})'.format(charid)
                logger.error(msg)
                chardetails['altof'] = 'Unknown'
        else:
            chardetails['altof'] = None
            chardetails['isalt'] = False

        ## start fetching character-specific information

        #
        request_url = 'characters/{0}/location/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

        if not code == 200:
            # it doesn't really matter
            msg = 'characters loction API error {0}: {1}'.format(code, result)
            logger.debug(msg)
            location = None
            chardetails['location_id'] = location
            chardetails['location'] = 'Unknown'
        else:
            # can include either station_id or structure_id
            location = result['solar_system_id']
            chardetails['location_id'] = location

        request_url = 'characters/{0}/location/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

        if not code == 200:
            # it doesn't really matter
            msg = 'characters loction API error {0}: {1}'.format(code, result)
            logger.debug(msg)
            location = None
        else:
            # can include either station_id or structure_id
            location = result['solar_system_id']

        chardetails['location_id'] = location

        # map the location to a name
        if location == None:
            chardetails['location'] = 'Unknown'
        else:
            request_url = 'universe/systems/{0}/'.format(location)
            code, result = common.request_esi.esi(__name__, request_url, 'get', version='v4')
            if not code == 200:
                msg = '{0} API error: {1}'.format(request_url, result)
                logger.error(msg)
                chardetails['location'] = 'Unknown'
            else:
                chardetails['location'] = result['name']

        # get online status

        request_url = 'characters/{0}/online/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v2')

        if not code == 200:
            # it doesn't really matter
            msg = '{0} API error: {1}'.format(request_url, result)
            logger.debug(msg)
            location = None
            chardetails['online'] = 'Unknown'
            chardetails['last_online'] = 'Unknown'
        else:
            chardetails['online'] = result['online']
            chardetails['last_online'] = result['last_login']
        try:
            request_url_corp = 'corporations/{0}/'.format(corp_id)
            code_corp, result_corp = common.request_esi.esi(__name__, request_url_corp, 'get')

            if not code_corp == 200:
                _logger.log('[' + __name__ + '] /corporations API error {0}: {1}'.format(code_corp, result_corp['error']), _logger.LogLevel.WARNING)
                msg = '{0} API error: {1}'.format(request_url_corp, result)
                logger.warning(msg)
            else:
                chardetails['corporation'] = result_corp['name']
        except KeyError as error:
            msg = 'corporation id does not exist: {0}'.format(corp_id)
            logger.error(msg)
            charname = None
    return chardetails


