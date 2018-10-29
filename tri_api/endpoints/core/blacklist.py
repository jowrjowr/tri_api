from tri_api import app
from flask import request, json, Response
import re
import time
import logging
import json
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import common.request_esi
import urllib
import requests
from common.logger import securitylog_new as securitylog

@app.route('/core/blacklist/confirmed', methods=[ 'GET' ])
def core_blacklist():

    # get all users that are confirmed blacklisted

    logger = logging.getLogger('tri_api.endpoints.blacklist.confirmed')

    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('charid')

    securitylog('viewed blacklist', detail='confirmed', ipaddress=ipaddress, charid=log_charid)

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='accountStatus=banned'
    attrlist=['characterName', 'uid', 'altOf', 'banApprovedBy', 'banApprovedOn', 'banReason', 'banReportedBy', 'banDescription', 'allianceName' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # start converting the bans into friendly information

    banlist = dict()

    for dn, info in result.items():
        charname = info['characterName']
        approver_charid = info['banApprovedBy']
        reporter_charid = info['banReportedBy']

        banlist[charname] = info
        # map the times to friendlier info

        if info['banApprovedOn']:
            banlist[charname]['banApprovedOn'] = time.strftime('%Y-%m-%d', time.localtime(info['banApprovedOn']))

        # how the fuck did ban reasons/descriptions get stored this way?!

        banlist[charname]['banReason'] = ban_convert(info['banReason'])

        # map the main of the banned alt to a name

        if info['altOf'] is not None:

            main_charid = info['altOf']

            banlist[charname]['isalt'] = True
            banlist[charname]['main_charid'] = main_charid

            main_name = _ldaphelpers.ldap_uid2name(main_charid)

            if main_name is False or None:

                request_url = 'characters/{0}/'.format(main_charid)
                code, result = common.request_esi.esi(__name__, request_url, 'get')

                if not code == 200:
                    msg = '/characters/{0}/ API error {1}: {2}'.format(charid, code, result)
                    logger.warning(msg)
                    banlist[charname]['main_charname'] = 'Unknown'
                else:
                    banlist[charname]['main_charname'] = result['name']
            else:
                banlist[charname]['main_charname'] = main_name
        else:
            banlist[charname]['isalt'] = False
            banlist[charname]['main_charname'] = None
            banlist[charname]['main_charid'] = None

        # map the reporter and approver's ids to names

        approver_name = _ldaphelpers.ldap_uid2name(approver_charid)
        reporter_name = _ldaphelpers.ldap_uid2name(reporter_charid)

        if not approver_name and approver_charid:
            # no longer in ldap?
            request_url = 'characters/{0}/'.format(approver_charid)
            code, result = common.request_esi.esi(__name__, request_url, 'get')
            if not code == 200:
                msg = '/characters/{0}/ API error {1}: {2}'.format(approver_charid, code, result)
                logger.warning(msg)
                banlist[charname]['banApprovedBy'] = 'Unknown'
            else:
                banlist[charname]['banApprovedBy'] = result['name']
        else:
            banlist[charname]['banApprovedBy'] = approver_name

        if not reporter_name and reporter_charid:
            request_url = 'characters/{0}/'.format(info['banReportedBy'])
            code, result = common.request_esi.esi(__name__, request_url, 'get')
            if not code == 200:
                msg = '/characters/{0}/ API error {1}: {2}'.format(reporter_charid, code, result)
                logger.warning(msg)
                banlist[charname]['banReportedBy'] = 'Unknown'
            else:
                banlist[charname]['banReportedBy'] = result['name']
        else:
            banlist[charname]['banReportedBy'] = reporter_name

    return Response(json.dumps(banlist), status=200, mimetype='application/json')

@app.route('/core/blacklist/pending', methods=[ 'GET' ])
def core_blacklist_pending():

    # get all users that are waiting to be blacklisted

    logger = logging.getLogger('tri_api.endpoints.blacklist.pending')

    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('charid')
    cookie = request.cookies.get('tri_core')

    securitylog('viewed blacklist', detail='pending', ipaddress=ipaddress, charid=log_charid)

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='authGroup=ban_pending'
    attrlist=['characterName', 'uid', 'altOf', 'banReason', 'banReportedBy', 'banDescription', 'banDate' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    # start converting the bans into friendly information

    banlist = dict()

    if result is None:
        # nothing pending
        return Response('{}', status=200, mimetype='application/json')


    for dn, info in result.items():
        charname = info['characterName']
        reporter_charid = info['banReportedBy']

        banlist[charname] = info
        # map the times to friendlier info

        if info['banDate']:
            banlist[charname]['banDate'] = time.strftime('%Y-%m-%d', time.localtime(info['banDate']))

        # map the main of the banned alt to a name

        if info['altOf'] is not None:

            main_charid = info['altOf']

            banlist[charname]['isalt'] = True
            banlist[charname]['main_charid'] = main_charid

            main_name = _ldaphelpers.ldap_uid2name(main_charid)

            if main_name is False or None:

                request_url = 'characters/{0}/'.format(main_charid)
                code, result = common.request_esi.esi(__name__, request_url, 'get')

                if not code == 200:
                    msg = '/characters API error {0}: {1}'.format(code, result)
                    logger.warning(msg)
                    banlist[charname]['main_charname'] = 'Unknown'
                else:
                    banlist[charname]['main_charname'] = result['name']
            else:
                banlist[charname]['main_charname'] = main_name
        else:
            banlist[charname]['main_charid'] = None
            banlist[charname]['main_charname'] = None
            banlist[charname]['isalt'] = False

        # map the reporter id to name

        reporter_name = _ldaphelpers.ldap_uid2name(reporter_charid)

        if not reporter_name and reporter_charid:
            request_url = 'characters/{0}/'.format(info['banReportedBy'])
            code, result = common.request_esi.esi(__name__, request_url, 'get')

            if not code == 200:
                msg = '/characters API error {0}: {1}'.format(code, result)
                logger.warning(msg)
                banlist[charname]['banReportedBy'] = 'Unknown'
            else:
                banlist[charname]['banReportedBy'] = result['name']
        else:
            banlist[charname]['banReportedBy'] = reporter_name

    return Response(json.dumps(banlist), status=200, mimetype='application/json')

@app.route('/core/blacklist/confirmall', methods=[ 'GET' ])
def core_blacklist_confirmall():

    # logging
    logger = logging.getLogger('tri_api.endpoints.blacklist.confirmall')

    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('charid')

    securitylog('blacklist bulk confirm', ipaddress=ipaddress, charid=log_charid, detail='EVERYONE')

    # fetch details including main + alts

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'authGroup=ban_pending'
    attrlist=['characterName', 'uid', 'altOf', 'authGroup', 'accountStatus' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        msg = 'no such charid {0}'.format(ban_charid)
        logger.warning(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=404, mimetype='application/json')

    for dn, info in result.items():
        charid = info['uid']
        msg = 'confirming {0}'.format(charid)
        core_blacklist_confirm(charid)
#        url = "https://api.triumvirate.rocks/core/blacklist/{0}/confirm?charid={1}&ipaddress={2}".format(charid, log_charid, ipaddress)
#        requests.get(url)

    # maybe not worth bothering?
    return Response({}, status=200, mimetype='application/json')

@app.route('/core/blacklist/<ban_charid>/confirm', methods=[ 'GET' ])
def core_blacklist_confirm(ban_charid):

    # promote someone from 'ban pending' to 'banned'

    # logging
    logger = logging.getLogger('tri_api.endpoints.blacklist.confirm')

    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('charid')

    if log_charid is None:
        log_charid = 90622096

    securitylog('blacklist confirm'.format(ban_charid), ipaddress=ipaddress, charid=log_charid, detail='charid {0}'.format(ban_charid))

    # fetch details including main + alts

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(|(altOf={0})(uid={0}))'.format(ban_charid)
    attrlist=['characterName', 'uid', 'altOf', 'authGroup', 'accountStatus' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        msg = 'no such charid {0}'.format(ban_charid)
        logger.warning(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=404, mimetype='application/json')

    for dn, info in result.items():

        # change account status and authgroup to banned
        # add an approved by/time

        # do sanity checks

        status = info['accountStatus']
        charname = info['characterName']
        altof = info['altOf']
        groups = info['authGroup']

        if status == 'banned':
            msg = 'user {0} already banned'.format(charname)
            logger.info(msg)
            return Response({}, status=200, mimetype='application/json')

        if 'ban_pending' not in groups and altof is None:
            # need the ban pending auth group
            msg = 'user {0} not pending ban confirmation'.format(charname)
            logger.info(msg)
            return Response({}, status=200, mimetype='application/json')
        else:
            msg = 'setting dn {0} to banned'.format(dn)
            logger.info(msg)

        # moving from pending to 'actually banned'
        _ldaphelpers.purge_authgroups(dn, ['ban_pending'])
        _ldaphelpers.update_singlevalue(dn, 'authGroup', 'banned')

        # actually ban
        _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'banned')
        _ldaphelpers.update_singlevalue(dn, 'banApprovedBy', log_charid)
        _ldaphelpers.update_singlevalue(dn, 'banApprovedOn', time.time())

    # all done
    return Response({}, status=200, mimetype='application/json')


@app.route('/core/blacklist/<charid>/remove', methods=[ 'GET' ])
def core_blacklist_remove(charid):

    # demote someone from the blacklist

    # logging
    logger = logging.getLogger('tri_api.endpoints.blacklist.remove')

    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('charid')

    # optional charid override for command line tinkering to record correctly

    securitylog('blacklist removal', ipaddress=ipaddress, charid=log_charid, detail='charid {0}'.format(charid))

    # fetch details

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='(|(altOf={0})(uid={0}))'.format(charid)
    attrlist=['characterName', 'uid', 'altOf', 'authGroup' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    if result == None:
        msg = 'charid {0} is not in core'.format(charid)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    for dn, info in result.items():

        purge = [ 'banApprovedBy', 'banApprovedOn', 'banDate', 'banReason', 'banReportedBy', 'banDescription' ]

        _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'public')
        _ldaphelpers.update_singlevalue(dn, 'authGroup', 'public')
        #_ldaphelpers.purge_authgroups(dn, [ 'banned', 'ban_pending' ])
        for attr in purge:
            _ldaphelpers.update_singlevalue(dn, attr, None)

    return Response({}, status=200, mimetype='application/json')

@app.route('/core/blacklist/add', methods=[ 'POST' ])
def core_blacklist_add():

    # put someone into the blacklist, pending confirmation

    # logging
    logger = logging.getLogger('tri_api.endpoints.blacklist.add')
    ipaddress = request.args.get('log_ip')
    log_charid = request.args.get('charid')

    # optional charid override for command line tinkering to record correctly

    # parse form data
    ban_data = dict()
    ban_data['banreason'] = request.form.get('reason')
    ban_data['bandescription'] = request.form.get('description')
    ban_data['main'] = request.form.get('charName')

    ban_data['alts'] = list()
    altfields = ['alt1', 'alt2', 'alt3', 'alt4', 'alt5', 'alt6', 'alt7']

    for alt in altfields:
        altname = request.form.get(alt)
        if altname is not None and altname != '':
            ban_data['alts'].append(altname)

    main_charname = ban_data['main']

    securitylog('blacklist add', ipaddress=ipaddress, charid=log_charid, detail='charname {0}'.format(main_charname))

    # batch search the main and alts

    chardata = dict()

    for charname in [ main_charname ] + ban_data['alts']:
        query = { 'categories': 'character', 'language': 'en-us', 'search': charname, 'strict': 'true' }
        query = urllib.parse.urlencode(query)
        request_url = 'search/?' + query
        code, result = common.request_esi.esi(__name__, request_url, 'get', version='v2')

        # will allow a hardfail for bans

        if result.get('character') is None:
            msg = 'unable to identify charname: {0}'.format(charname)
            logger.error(msg)
            js = json.dumps({ 'error': msg })
            return Response(js, status=400, mimetype='application/json')
        if len(result.get('character')) > 1:
            msg = 'more than one return for charname {0} from ESI search'.format(main_charname)
            logger.warning(msg)

        # even on a single result its still a list

        for charid in result.get('character'):
            chardata[charname] = charid

    # ban the main

    main_charid = chardata[main_charname]
    result = ban_character(main_charid)

    if not result:
        msg = 'unable to ban character {0}'.format(main_charname)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=400, mimetype='application/json')

    # tag the ban with flavor text

    cn, dn = _ldaphelpers.ldap_normalize_charname(main_charname)

    _ldaphelpers.add_value(dn, 'banReason', ban_data['banreason'])
    _ldaphelpers.add_value(dn, 'banDescription', ban_data['bandescription'])
    _ldaphelpers.add_value(dn, 'banReportedBy', log_charid)
    _ldaphelpers.add_value(dn, 'banDate', time.time())

    # try to find registered alts and ban those too

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='altOf={}'.format(main_charid)
    attrlist=['characterName', 'uid', 'altOf', 'accountStatus' ]
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        js = json.dumps({ 'error': msg })
        return Response(js, status=500, mimetype='application/json')

    error = False

    if result:
        for dn, info in result.items():
            charid = info['uid']
            charname = info['characterName']
            ban_result = ban_character(main_charid)
            if not result:
                msg = 'unable to ban character {0}'.format(charname)
                js = json.dumps({ 'error': msg })
                logger.error(msg)
                error = True

    # work through the submitted alts and ban those too

    if len(ban_data['alts']) == 0:
        # were done here.
        if not error:
            return Response({}, status=200, mimetype='application/json')
        else:
            return Response(js, status=400, mimetype='application/json')

    msg = 'banning {0} {1} alts'.format(len(ban_data['alts']), main_charname)
    logger.info(msg)

    for alt_charname in ban_data['alts']:
        alt_charid = chardata[alt_charname]
        ban_result = ban_character(alt_charid, altof=main_charid)

        if not ban_result:
            msg = 'unable to ban {0} alt {1}'.format(main_charname, alt_charname)
            logger.error(msg)
            js = json.dumps({ 'error': msg })
            error = True
            # keep trying tho

    if not error:
        return Response({}, status=200, mimetype='application/json')
    else:
        return Response(js, status=400, mimetype='application/json')

def ban_character(charid, altof=None):
    # take a charid and ban it (technially, set it to pending approval)
    # flavor text added in other logic

    logger = logging.getLogger('tri_api.endpoints.blacklist.add.character')

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr='uid={}'.format(charid)
    attrlist=['characterName']
    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        msg = 'unable to fetch ldap information: {}'.format(error)
        logger.error(msg)
        return False

    # if a stub is created, i would have to search again

    affiliations = _esihelpers.esi_affiliations(charid)

    charname = affiliations['charname']

    cn, dn = _ldaphelpers.ldap_normalize_charname(charname)

    if result == None:
        # not currently in ldap, create a stub
        _ldaphelpers.ldap_create_stub(charid=charid, authgroups=['public', 'ban_pending'], altof=altof)
    else:
        _ldaphelpers.add_value(dn, 'authGroup', 'ban_pending')

    msg = 'banning {0}'.format(charname)
    logger.info(msg)

    return True

def ban_convert(reason):
    # legacy blacklist stuff was stored as an enum

    if reason == 1:
        return "shitlord"
    elif reason == 2:
        return "spy"
    elif reason == 3:
        return "rejected applicant"
    elif reason == 4:
        return "other"
    else:
        return reason
