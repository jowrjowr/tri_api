from tri_api import app
from flask import request, Response, session, redirect, make_response, json

import datetime
import uuid
import time
import requests
import common.logger as _logger
import common.credentials.eve as _eve
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
from common.check_scope import check_scope

import tri_core.common.session as _session

from tri_core.common.register import registeruser
from tri_core.common.storetokens import storetokens
from tri_core.common.scopes import scope, blue_scope, renter_scope
from tri_core.common.session import readsession
from tri_core.common.testing import vg_blues, vg_alliances, vg_renters

from requests_oauthlib import OAuth2Session

@app.route('/auth/eve/register/renter', methods=['GET'])
def auth_evesso_renter():
    return evesso(renter=True)

@app.route('/auth/eve/register/blue', methods=['GET'])
def auth_evesso_blue():
    return evesso(tempblue=True)

@app.route('/auth/eve/register', methods=['GET'])
def auth_evesso():
    return evesso()

@app.route('/auth/eve/register/alt', methods=['GET'])
def auth_evesso_alt():

    cookie = request.cookies.get('tri_core')

    if cookie == None:
        return make_response('You need to be logged in with your main in order to register an alt<br>Try logging into CORE again<br>')
    else:
        payload = readsession(cookie)
        return evesso(isalt=True, altof=payload['charID'])

def evesso(isalt=False, altof=None, tempblue=False, renter=False):

    client_id = _eve.client_id
    client_secret = _eve.client_secret
    redirect_url = _eve.redirect_url

    base_url = 'https://login.eveonline.com'
    token_url = base_url + '/v2/oauth/token'
    base_auth_url = base_url + '/v2/oauth/authorize'

    # security logging

    ipaddress = request.headers['X-Real-Ip']
    if isalt == True:
        _logger.securitylog(__name__, 'SSO login initiated', ipaddress=ipaddress, detail='alt of {}'.format(altof))
        auth_scopes = scope
    elif tempblue == True:
        _logger.securitylog(__name__, 'SSO login initiated', ipaddress=ipaddress, detail='temp blue')
        # the scope list for temp blues is very short
        auth_scopes = blue_scope
    elif renter == True:
        _logger.securitylog(__name__, 'SSO login initiated', ipaddress=ipaddress, detail='renter')
        # the renter scope list is distinct
        auth_scopes = renter_scope
    else:
        auth_scopes = scope
        _logger.securitylog(__name__, 'SSO login initiated', ipaddress=ipaddress)

    # setup the redirect url for the first stage of oauth flow

    oauth_session = OAuth2Session(
        client_id=client_id,
        scope=auth_scopes,
        redirect_uri=redirect_url,
        auto_refresh_kwargs={
            'client_id': client_id,
            'client_secret': client_secret,
        },
        auto_refresh_url=token_url,
    )
    auth_url, state = oauth_session.authorization_url(
        base_auth_url,
        isalt=isalt,
        altof=altof,
        renter=renter,
        tempblue=tempblue,
        )

    # store useful parameters in oauth state

    session['tempblue'] = tempblue
    session['oauth2_state'] = state
    session['isalt'] = isalt
    session['altof'] = altof
    session['renter'] = renter

    return redirect(auth_url, code=302)

@app.route('/auth/eve/callback', methods=['GET'])
def auth_evesso_callback():

    client_id = _eve.client_id
    client_secret = _eve.client_secret
    redirect_url = _eve.redirect_url

    base_url = 'https://login.eveonline.com'
    token_url = base_url + '/v2/oauth/token'
    verify_url = base_url + '/oauth/verify'

    # the user has (ostensibly) authenticated with the application, now
    # the access token can be fetched

    altof = session.get('altof')
    isalt = session.get('isalt')
    tempblue = session.get('tempblue')
    renter = session.get('renter')
    state = session.get('oauth2_state')
    ipaddress = request.headers['X-Real-Ip']

    # security logging

    if isalt == True:
        _logger.securitylog(__name__, 'SSO callback received', ipaddress=ipaddress, detail='alt of {}'.format(altof))
        auth_scopes = scope
    elif tempblue == True:
        _logger.securitylog(__name__, 'SSO callback received', ipaddress=ipaddress, detail='temp blue')
        # make sure we only check for the blue scope list
        auth_scopes = blue_scope
    elif renter == True:
        _logger.securitylog(__name__, 'SSO callback received', ipaddress=ipaddress, detail='renter')
        auth_scopes = renter_scope
    else:
        _logger.securitylog(__name__, 'SSO callback received', ipaddress=ipaddress)
        auth_scopes = scope

    # handle oauth token manipulation

    oauth_session = OAuth2Session(
        client_id=client_id,
        state=state,
        redirect_uri=redirect_url,
        auto_refresh_kwargs={
            'client_id': client_id,
            'client_secret': client_secret,
        },
        auto_refresh_url=token_url,
    )

    headers = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }
    try:
        atoken = oauth_session.fetch_token(
            token_url,
            client_secret=client_secret,
            authorization_response=request.url,
            headers=headers,
        )

    except Exception as error:
        _logger.log('[' + __name__ + '] unable to fetch eve sso access token: {0}'.format(error),_logger.LogLevel.ERROR)
        return('ERROR: ' + str(error))

    access_token = atoken['access_token']
    refresh_token = atoken['refresh_token']
    expires_at = atoken['expires_at']

    headers = {'Authorization': 'Bearer ' + access_token }
    result = requests.get(verify_url, headers=headers)

    try:
        result.raise_for_status()
    except requests.exceptions.HTTPError as error:
        msg = 'unable to verify eve sso access token: {0}'.format(error)
        _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
        message = 'SORRY, internal error. Try again.'
        response = make_response(message)

        return response

    ## fetch the information for later checking

    # token data

    tokendata = json.loads(result.text)
    charid = tokendata['CharacterID']
    tokentype = tokendata['TokenType']
    expires_at = tokendata['ExpiresOn']
    charname = tokendata['CharacterName']

    # full ESI affiliations

    affilliations = _esihelpers.esi_affiliations(charid)

    if affilliations.get('error'):
        msg = 'error in fetching affiliations for {0}: {1}'.format(charid, affilliations.get('error'))
        _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
        message = 'SORRY, internal error. Try again.'
        response = make_response(message)
        return response

    allianceid = affilliations.get('allianceid')
    alliancename = affilliations.get('alliancename')
    corpid = affilliations.get('corpid')

    # ldap, if any

    userinfo = _ldaphelpers.ldap_userinfo(charid)

    # get alt status, if any, from ldap
    if userinfo and not isalt:
        altof = userinfo.get('altOf')

        if altof is not None:
            isalt = True

    # what the fuck is going on
    # this is a check that _shouldnt_ trigger anymore

    if isalt:
        if altof == None or altof == 'None':
            msg = 'is an alt but altof = None? wtf. charid {0} altof {1} {2}'.format(charid, altof, type(altof))
            _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
            msg = 'error in fetching alt information. please poke saeka.'
            response = make_response(msg)
            return response

    # fix authgroup to an empty array in case nothing

    if not userinfo:
        authgroups = []
    else:
        authgroups = userinfo.get('authGroup')
        if authgroups is None:
            authgroups = []

    # verify that the atoken we get actually has the correct scopes that we requested
    # just in case someone got cute and peeled some off.

    code, result = check_scope(__name__, charid, auth_scopes, atoken=access_token)

    if code == 'error':
        # something in the check broke
        msg = 'error in testing scopes for {0}: {1}'.format(charid, result)
        _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
        message = 'SORRY, internal error. Try again.'
        response = make_response(message)
        return response

    elif code == False:
        # the user peeled something off the scope list. naughty.
        msg = 'user {0} modified scope list. missing: {1}'.format(charid, result)
        _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.WARNING)

        _logger.securitylog(__name__, 'core login scope modification', charid=charid, ipaddress=ipaddress)

        message = "Don't tinker with the scope list, please.<br>"
        message += "If you have an issue with it, talk to triumvirate leadership."
        response = make_response(message)
        return response
    elif code == True:
        # scopes validate
        _logger.log('[' + __name__ + '] user {0} has expected scopes'.format(charid, result),_logger.LogLevel.DEBUG)

        # register the user, store the tokens

        registeruser(charid, access_token, refresh_token, tempblue=tempblue, isalt=isalt, altof=altof, renter=renter)


    ## TESTS
    ##
    ## check affiliations and for bans

    # check to see if the user is banned

    if 'banned' in authgroups:
        # banned users not allowed under any conditions
        message = 'nope.avi'
        if isalt == True:
            msg = 'banned user {0} ({1}) tried to register alt {2}'.format(charid, charname, altof)
            _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.WARNING)
            _logger.securitylog(__name__, 'banned user tried to register', charid=charid, ipaddress=ipaddress, detail='alt of {0}'.format(altof))
        else:
            msg = 'banned user {0} ({1}) tried to register'.format(charid, charname)
            _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.WARNING)
            _logger.securitylog(__name__, 'banned user tried to register', charid=charid, ipaddress=ipaddress)
        return make_response(message)


    # only tri & blues are allowed to use auth
    if allianceid not in vg_blues() and allianceid not in vg_alliances() and allianceid not in vg_renters():
        if not isalt:
            # not an alt, not a blue. not a renter. go away.
            msg = 'please contact a recruiter if you are interested in joining triumvirate'
            logmsg = 'non-blue user {0} ({1}) tried to register'.format(charid, charname)
            _logger.log('[' + __name__ + '] {0}'.format(logmsg),_logger.LogLevel.WARNING)
            _logger.securitylog(__name__, 'non-blue user tried to register', charid=charid, ipaddress=ipaddress)
            return make_response(msg)
        else:
            # someone is registering a non-blue alt, nbd
            pass

    # make sure the temp blue endpoint not being used by tri proper
    if tempblue:
        # this is a tri blue, but not tri proper.
        # ...or at least ought to be.
        if allianceid in vg_alliances():
            # naughty! but not worth logging
            msg = 'please use the other login endpoint. <br>'
            msg += 'this is a lower privileged one for blues <b>ONLY</b>'
            return make_response(msg)

    # is this a temp blue trying to login with the wrong endpoint?
    if allianceid in vg_blues():
        if not tempblue:
            # no big deal. we got extra scopes for it.
            tempblue = True

    # the user has passed the various exclusions, gg

    # security logging

    msg = 'SSO callback completed'
    if isalt == True:
        _logger.securitylog(__name__, msg, charid=charid, ipaddress=ipaddress)
    elif tempblue == True:
        _logger.securitylog(__name__, msg, charid=charid, ipaddress=ipaddress, detail='blue from {0}'.format(alliancename))
    elif renter == True:
        _logger.securitylog(__name__, msg, charid=charid, ipaddress=ipaddress, detail='renter from {0}'.format(alliancename))
    else:
        _logger.securitylog(__name__, msg, charid=charid, ipaddress=ipaddress, detail='alt of {0}'.format(altof))

    expire_date = datetime.datetime.now() + datetime.timedelta(days=14)

    # build the cookie and construct the http response

    if isalt == True:
        # if the character being logged in is an alt, make a session for the main.

        if userinfo:
            # the alt is alredy registered. go to homepage.
            response = make_response(redirect('https://www.triumvirate.rocks'))
        else:
            # go to alt registration page to show update.
            response = make_response(redirect('https://www.triumvirate.rocks/altregistration'))

        cookie = _session.makesession(altof)
        _logger.log('[' + __name__ + '] created session for user: {0} (alt of {1})'.format(charname, altof),_logger.LogLevel.INFO)
    else:
        # proceed normally otherwise
        response = make_response(redirect('https://www.triumvirate.rocks'))
        cookie = _session.makesession(charid)
        _logger.log('[' + __name__ + '] created session for user: {0} (charid {1})'.format(charname, charid),_logger.LogLevel.INFO)

    response.set_cookie('tri_core', cookie, domain='.triumvirate.rocks', expires=expire_date)

    if cookie == False:
        # unable to construct session cookie
        _logger.log('[' + __name__ + '] error in creating session cookie for user {0}'.format(charid),_logger.LogLevel.ERROR)
        message = 'SORRY, internal error. Try again.'
        return make_response(message)

    # handle registered users

    if userinfo is not None:
        # already in ldap, and not banned

        if isalt:
            # is a registered alt
            _logger.log('[' + __name__ + '] alt user {0} (alt of {1}) already registered'.format(charname, altof),_logger.LogLevel.INFO)
            _logger.securitylog(__name__, 'core login', charid=charid, ipaddress=ipaddress, detail='via alt {0}'.format(altof))
            code, result = _ldaphelpers.ldap_altupdate(__name__, altof, charid)
            return response
        else:
            if tempblue:
                # registered blue main.
                _logger.log('[' + __name__ + '] user {0} ({1}) already registered'.format(charid, charname),_logger.LogLevel.INFO)
                _logger.securitylog(__name__, 'core login', charid=charid, ipaddress=ipaddress, detail='blue from {0}'.format(alliancename))
                code, result = _ldaphelpers.ldap_altupdate(__name__, altof, charid)
                return response
            else:
                # registered character
                _logger.log('[' + __name__ + '] user {0} ({1}) already registered'.format(charid, charname),_logger.LogLevel.INFO)
                _logger.securitylog(__name__, 'core login', charid=charid, ipaddress=ipaddress)
                code, result = _ldaphelpers.ldap_altupdate(__name__, altof, charid)
                return response

    # after this point, the only folks that are left are unregistered users

    # handle new temp blues
    if tempblue:
        _logger.log('[' + __name__ + '] user {0} ({1}) not registered'.format(charid, charname),_logger.LogLevel.INFO)
        _logger.securitylog(__name__, 'core user registered', charid=charid, ipaddress=ipaddress, detail='blue from {0}'.format(alliancename))
        return response

    # handle new renters
    if renter:
        _logger.log('[' + __name__ + '] user {0} ({1}) not registered'.format(charid, charname),_logger.LogLevel.INFO)
        _logger.securitylog(__name__, 'core user registered', charid=charid, ipaddress=ipaddress, detail='renter from {0}'.format(alliancename))
        return response

    # handle new alts

    if isalt:
        _logger.log('[' + __name__ + '] alt user {0} (alt of {1}) not registered'.format(charname, altof),_logger.LogLevel.INFO)
        _logger.securitylog(__name__, 'alt user registered', charid=charid, ipaddress=ipaddress, detail='alt of {0}'.format(altof))
        return response
    else:
        _logger.log('[' + __name__ + '] user {0} ({1}) not registered'.format(charid, charname),_logger.LogLevel.INFO)
        _logger.securitylog(__name__, 'core user registered', charid=charid, ipaddress=ipaddress)
        return response
