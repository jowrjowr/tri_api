import common.logger as _logger
import common.maint.eve.refresh as _everefresh
import common.maint.discord.refresh as _discordrefresh
import common.ldaphelpers as _ldaphelpers
import common.request_esi
import time
import ldap

from tri_core.common.storetokens import storetokens
from concurrent.futures import ThreadPoolExecutor, as_completed

def maint_tokens():

    ldap_conn = _ldaphelpers.ldap_binding(__name__)

    if ldap_conn == None:
        _logger.log('[' + __name__ + '] LDAP connection error: {}'.format(error),_logger.LogLevel.ERROR)
        return

    # grab each token from ldap

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(|(esiRefreshToken=*)(discordRefreshToken=*))'
    attrlist = ['esiRefreshToken', 'esiAccessTokenExpires', 'discordRefreshToken', 'discordAccessTokenExpires', 'discorduid', 'esiScope', 'uid', 'corporationRole']

    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        return

    _logger.log('[' + __name__ + '] ldap users with defined refresh tokens: {0}'.format(len(result)),_logger.LogLevel.INFO)

    evetokens = dict()
    discordtokens = dict()

    for dn, info in result.items():

        eve_rtoken = info.get('esiRefreshToken')
        discord_rtoken = info.get('discordRefreshToken')
        evetokens[dn] = dict()
        discordtokens[dn] = dict()

        if eve_rtoken is not None:

            evetokens[dn]['rtoken'] = eve_rtoken
            evetokens[dn]['uid'] = int( info.get('uid') )
            evetokens[dn]['scopes'] = info.get('esiScope')
            evetokens[dn]['roles'] = info.get('corporationRole')
            evetokens[dn]['expires'] = info.get('esiAccessTokenExpires')

        if discord_rtoken is not None:

            discordtokens[dn]['rtoken'] = discord_rtoken
            discordtokens[dn]['expires'] = float( info.get('discordAccessTokenExpires') )
            discordtokens[dn]['uid'] = int( info.get('uid') )
            discordtokens[dn]['discorduid'] = int( info.get('discorduid') )


    ldap_conn.unbind()

    # dump the tokens into a pool to bulk manage

    with ThreadPoolExecutor(40) as executor:
        futures = { executor.submit(tokenthings, dn, evetokens[dn], discordtokens[dn]): dn for dn in evetokens.keys() }
        for future in as_completed(futures):
            data = future.result()


def tokenthings(dn, evetokens, discordtokens):

    # retries

    retry_max = 5
    sleep = 1
    function = __name__

    tokens = ['eve', 'discord']

    for token_type in tokens:

        retry_count = 0
        done = False
        while (retry_count < retry_max and not done):

            if retry_count > 0:
                _logger.log('[' + function + '] {0} token update retry {1} of {2}'.format(token_type, retry_count, retry_max), _logger.LogLevel.WARNING)

            if token_type == 'eve':
                result = eve_tokenthings(dn, evetokens)
            if token_type == 'discord':
                result = discord_tokenthings(dn, discordtokens)

            retry_count += 1

            if result:
                # success, all done.
                done = True
            else:
                _logger.log('[' + function + '] {0} token update failed. sleeping {1} seconds before retrying'.format(token_type, sleep), _logger.LogLevel.WARNING)
                time.sleep(sleep)

            if retry_count == retry_max:
                _logger.log('[' + function + '] {0} token update failed {1} times. giving up. '.format(token_type, retry_max), _logger.LogLevel.WARNING)

def discord_tokenthings(dn, discordtokens):

    old_rtoken = discordtokens.get('rtoken')
    expires = discordtokens.get('expires')
    charid = discordtokens.get('uid')
    discorduid = discordtokens.get('discorduid')

    if not old_rtoken:
        return True

    # do we even bother refreshing?

    if expires is not None and old_rtoken is not None:
        difference = expires - time.time()
        if difference > 3600:
            return True

    result, code = _discordrefresh.refresh_token(old_rtoken)

    if code is not True:
        # broken token, or broken oauth?
        # the distinction matters.
        # see env/lib/python3.5/site-packages/oauthlib/oauth2/rfc6749/errors.py

        _logger.log('[' + __name__ + '] unable to refresh discord token for {0}: {1}'.format(dn, result), _logger.LogLevel.INFO)

        # only these exception types are valid reasons to purge a token
        purgetype = [ 'InvalidGrantError', 'UnauthorizedClientError', 'InvalidClientError' ]

        if result in purgetype:

            # purge the entry from the ldap user

            _ldaphelpers.update_singlevalue(dn, 'discordRefreshToken', None)
            _ldaphelpers.update_singlevalue(dn, 'discordAccessToken', None)
            _ldaphelpers.update_singlevalue(dn, 'discordAccessTokenExpires', None)

            _logger.log('[' + __name__ + '] invalid discord token entries purged for user {}'.format(dn), _logger.LogLevel.INFO)
            return True

        # either way, this has failed

        ldap_conn.unbind()
        return False

    atoken = result.get('access_token')
    rtoken = result.get('refresh_token')
    expires = result.get('expires_at')

    # store the updated token
    result, value = storetokens(charid, atoken, rtoken, expires, token_type='discord')

    if result == False:
        _logger.log('[' + __name__ + '] unable to store discord tokens for user {}'.format(dn), _logger.LogLevel.ERROR)
        ldap_conn.unbind()
        return False

    # fetch the discord uid and store that too
    request_url = '/users/@me'
    code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v6', base='discord')

    if not code == 200:
        error = 'unable to get discord user information for {0}: ({1}) {2}'.format(dn, code, result['error'])
        _logger.log('[' + __name__ + '] ' + error,_logger.LogLevel.ERROR)
        return False

    new_discorduid = result.get('id')

    try:
        new_discorduid = int(new_discorduid)
    except Exception as e:
        return False

    # don't bother updating the uid unless it changes
    if discorduid != new_discorduid:
        _ldaphelpers.update_singlevalue(dn, 'discorduid', new_discorduid)

    return True

def eve_tokenthings(dn, evetokens):

    charid = evetokens.get('uid')
    roles = evetokens.get('roles')
    ldap_scopes = evetokens.get('scopes')
    old_rtoken = evetokens.get('rtoken')
    function = __name__

    if not old_rtoken:
        return True

    ldap_conn = _ldaphelpers.ldap_binding(__name__)

    if ldap_conn == None:
        msg = 'LDAP connection error: {}'.format(error)
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
        return False

    if roles is None:
        roles = []
    if ldap_scopes is None:
        ldap_scopes = []

    msg = 'updating eve token for charid {0}'.format(charid)
    _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.DEBUG)

    result, code = _everefresh.refresh_token(old_rtoken)

    if code is not True:
        # broken token, or broken oauth?
        # the distinction matters.
        # see env/lib/python3.5/site-packages/oauthlib/oauth2/rfc6749/errors.py

        msg = 'unable to refresh token for charid {0}: {1}'.format(charid, result)
        _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.INFO)

        # only these exception types are valid reasons to purge a token
        purgetype = [ 'InvalidGrantError', 'UnauthorizedClientError', 'InvalidClientError' ]

        if result in purgetype:

            # purge the entry from the ldap user

            mod_attrs = []
            mod_attrs.append((ldap.MOD_REPLACE, 'esiRefreshToken', None ))
            mod_attrs.append((ldap.MOD_REPLACE, 'esiAccessToken', None ))
            mod_attrs.append((ldap.MOD_REPLACE, 'esiAccessTokenExpires', None ))
            try:
                ldap_conn.modify_s(dn, mod_attrs)
            except ldap.LDAPError as error:
                msg = 'unable to purge eve token entries for {0}: {1}'.format(dn, error)
                _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.ERROR)
                ldap_conn.unbind()
                return False

            ldap_conn.unbind()
            return True
            msg = 'invalid token entries purged for user {}'.format(dn)
            _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.INFO)

        # either way, this has failed

        ldap_conn.unbind()
        return False

    atoken = result.get('access_token')
    rtoken = result.get('refresh_token')
    expires = result.get('expires_at')

    # store the updated token
    result, value = storetokens(charid, atoken, rtoken, expires, token_type='esi')

    if result == False:
        _logger.log('[' + __name__ + '] unable to store tokens for user {}'.format(dn), _logger.LogLevel.ERROR)
        ldap_conn.unbind()
        return False

    # the updated token is now in LDAP

    mod_attrs = []

    # fetch all corporation roles for the updated token

    request_url = 'characters/{0}/roles/?datasource=tranquility'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v1')

    if code == 403:
        error = 'no perms to read roles for {0}: ({1}) {2}'.format(charid, code, result['error'])
        _logger.log('[' + function + '] ' + error,_logger.LogLevel.DEBUG)
    elif not code == 200:
        error = 'unable to get character roles for {0}: ({1}) {2}'.format(charid, code, result['error'])
        _logger.log('[' + function + '] ' + error,_logger.LogLevel.ERROR)
    else:

        # figure out what needs to be added and removed from ldap

        missing_roles = set(result) - set(roles)
        extra_roles = set(roles) - set(result)

        for missing in list(missing_roles):
            missing = missing.encode('utf-8')
            mod_attrs.append((ldap.MOD_ADD, 'corporationRole', [ missing ] ))

        for extra in list(extra_roles):
            extra = extra.encode('utf-8')
            mod_attrs.append((ldap.MOD_DELETE, 'corporationRole', [ extra ] ))

    # determine the scopes the token has access to
    # the verify url is specifically not versioned
    # the token parameter is to bypass caching

    verify_url = 'verify/?datasource=tranquility&token={0}'.format(atoken)
    code, result = common.request_esi.esi(__name__, verify_url, method='get', base='esi_verify')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get token information for {0}: {1}'.format(charid, result['error']),_logger.LogLevel.ERROR)
        ldap_conn.unbind()
        return

    # character scopes come out in a space delimited list
    token_scopes = result['Scopes']
    token_scopes = token_scopes.split()
    token_charid = int(result['CharacterID'])

    if not token_charid == charid:
        _logger.log('[' + __name__ + '] stored token for charid {0} belongs to charid {1}'.format(charid, token_charid),_logger.LogLevel.ERROR)
        ldap_conn.unbind()
        return
    # so given an array of scopes, let's check that what we want is in the list of scopes the character's token has

    missing_scopes = set(token_scopes) - set(ldap_scopes)
    extra_scopes = set(ldap_scopes) - set(token_scopes)

    for missing in list(missing_scopes):
        missing = missing.encode('utf-8')
        mod_attrs.append((ldap.MOD_ADD, 'esiScope', [ missing ]))

    for extra in list(extra_scopes):
        extra = extra.encode('utf-8')
        mod_attrs.append((ldap.MOD_DELETE, 'esiScope', [ extra ] ))

    if len(mod_attrs) > 0:
        try:
            ldap_conn.modify_s(dn, mod_attrs)
        except ldap.LDAPError as error:
            _logger.log('[' + __name__ + '] unable to update uid {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
            return False
    ldap_conn.unbind()

    return True
