from flask import session, redirect, make_response, request
from tri_api import app

@app.route('/auth/discord/register', methods=['GET'])
def auth_discord_register():

    from requests_oauthlib import OAuth2Session

    import common.logger as _logger
    import common.credentials.discord as _discord
    from tri_core.common.session import readsession

    # fetch the tri core session so we can tie this to a charid

    cookie = request.cookies.get('tri_core')

    if cookie == None:
        msg = 'You need to be logged into tri core with your main in order to register on discord'
        msg += '<br>'
        msg += 'Try logging into CORE again<br>'
        return make_response(msg)

    payload = readsession(cookie)

    if payload == False:
        msg = 'There was a problem reading your tri core cookie.'
        msg += '<br>'
        msg += 'Try logging into CORE again<br>'
        return make_response(msg)

    charid = payload['charID']
    # security logging

    ipaddress = request.headers['X-Real-Ip']
    _logger.securitylog(__name__, 'discord registration initiated', ipaddress=ipaddress, charid=charid)

    client_id = _discord.client_id
    client_secret = _discord.client_secret
    redirect_url = _discord.redirect_url
    base_url = _discord.base_url

    base_auth_url = base_url + '/oauth2/authorize'
    token_url = base_url + '/oauth2/token'

    # setup the redirect url for the first stage of oauth flow
    # sadly none of the other discord scopes are useful
    # https://discordapp.com/developers/docs/reference

    scope = ['identify', 'connections', 'guilds']

    oauth_session = OAuth2Session(
        client_id=client_id,
        scope=scope,
        redirect_uri=redirect_url,
        auto_refresh_kwargs={
            'client_id': client_id,
            'client_secret': client_secret,
        },
        auto_refresh_url=token_url,
    )
    auth_url, state = oauth_session.authorization_url(base_auth_url)
    session['oauth2_state'] = state

    return redirect(auth_url, code=302)

@app.route('/auth/discord/callback', methods=['GET'])
def auth_discord_callback():

    from requests_oauthlib import OAuth2Session
    import common.logger as _logger
    import common.credentials.discord as _discord
    import tri_core.common.storetokens as _storetokens
    import common.ldaphelpers as _ldaphelpers
    import common.request_esi

    from tri_core.common.session import readsession

    # constants

    client_id = _discord.client_id
    client_secret = _discord.client_secret
    redirect_url = _discord.redirect_url
    base_url = _discord.base_url

    token_url = base_url + '/oauth2/token'
    base_auth_url = base_url + '/oauth2/authorize'


    # fetch the tri core session so we can tie this to a charid
    # we're re-verifying!

    cookie = request.cookies.get('tri_core')

    if cookie == None:
        msg = 'You need to be logged into tri core with your main in order to register on discord'
        msg += '<br>'
        msg += 'Try logging into CORE again<br>'
        return make_response(msg)

    payload = readsession(cookie)

    if payload == False:
        msg = 'There was a problem reading your tri core cookie.'
        msg += '<br>'
        msg += 'Try logging into CORE again<br>'
        return make_response(msg)

    charid = payload['charID']

    # security logging

    ipaddress = request.headers['X-Real-Ip']
    _logger.log('[' + __name__ + '] discord registration for charid {0} received'.format(charid),_logger.LogLevel.INFO)
    _logger.securitylog(__name__, 'discord registration initiated', ipaddress=ipaddress, charid=charid)

    # the user has (ostensibly) authenticated with the application, now
    # the access token can be fetched

    oauth_session = OAuth2Session(
        client_id=client_id,
        state=session.get('oauth2_state'),
        redirect_uri=redirect_url,
        auto_refresh_kwargs={
            'client_id': client_id,
            'client_secret': client_secret,
        },
        auto_refresh_url=token_url,
    )

    try:
        result = oauth_session.fetch_token(
            token_url,
            client_secret=client_secret,
            authorization_response=request.url,
        )
    except Exception as error:
        _logger.log('[' + __name__ + '] unable to fetch discord access token: {0}'.format(error),_logger.LogLevel.ERROR)
        return('ERROR: ' + str(error))

    atoken = result['access_token']
    rtoken = result['refresh_token']
    expires = result['expires_at']

    # store the discord token

    _storetokens.storetokens(charid, atoken, rtoken, expires, token_type='discord')

    _logger.log('[' + __name__ + '] discord registration complete',_logger.LogLevel.INFO)
    discord_widget = '<iframe src="https://discordapp.com/widget?id=358117641724100609&theme=dark" width="350" height="500" allowtransparency="true" frameborder="0"></iframe>'
    message = "You are done.<br> Connect to discord if you have not already<br>"
    message += discord_widget
    return message
