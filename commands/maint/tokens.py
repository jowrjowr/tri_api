import common.maint.eve.refresh as _everefresh
import common.maint.discord.refresh as _discordrefresh
import common.ldaphelpers as _ldaphelpers
import common.request_esi
import time
import ldap

from common.verify import verify
from tri_core.common.storetokens import storetokens
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.logger import getlogger_new as getlogger

def maint_tokens():

    logger = getlogger('maint.tokens')

    # do esi status check first

    request_url = 'status'
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v1')

    if not code == 200:
        error = 'ESI offline'
        logger.error(error)
        return

    # grab each token from ldap

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(|(esiRefreshToken=*)(discordRefreshToken=*))'
    attrlist = ['esiRefreshToken', 'esiAccessTokenExpires', 'discordRefreshToken', 'discordAccessTokenExpires', 'discorduid', 'esiScope', 'uid', 'corporationRole']

    code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

    if code == False:
        return

    msg = 'ldap users with defined refresh tokens: {0}'.format(len(result))
    logger.info(msg)

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

            if info.get('discorduid'):
                discordtokens[dn]['discorduid'] = int( info.get('discorduid') )

    # dump the tokens into a pool to bulk manage

    with ThreadPoolExecutor(40) as executor:
        futures = { executor.submit(tokenthings, dn, evetokens[dn], discordtokens[dn]): dn for dn in evetokens.keys() }
        for future in as_completed(futures):
            data = future.result()

def tokenthings(dn, evetokens, discordtokens):

    logger = getlogger('maint.tokens.tokenthings')

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
                msg = '{0} token update retry {1} of {2}'.format(token_type, retry_count, retry_max)
                logger.warning(msg)

            if token_type == 'eve':
                result = eve_tokenthings(dn, evetokens)
            if token_type == 'discord':
                result = discord_tokenthings(dn, discordtokens)

            retry_count += 1

            if result:
                # success, all done.
                done = True
            else:
                msg = '{0} token update failed. sleeping {1} seconds before retrying'.format(token_type, sleep)
                logger.warning(msg)
                time.sleep(sleep)

            if retry_count == retry_max:
                msg = '{0} token update failed {1} times. giving up. '.format(token_type, retry_max)
                logger.warning(msg)

def discord_tokenthings(dn, discordtokens):

    logger = getlogger('maint.tokens.discord')

    old_rtoken = discordtokens.get('rtoken')
    expires = discordtokens.get('expires')
    charid = discordtokens.get('uid')
    discorduid = discordtokens.get('discorduid')

    if not old_rtoken:
        return True

    if expires:
        current_time = time.time()
        if expires - current_time > 86400:
            return True

    result, code = _discordrefresh.refresh_token(old_rtoken)

    if code is not True:
        # broken token, or broken oauth?
        # the distinction matters.
        # see env/lib/python3.5/site-packages/oauthlib/oauth2/rfc6749/errors.py

        msg = 'unable to refresh discord token for {0}: {1}'.format(dn, result)
        logger.info(msg)

        # only these exception types are valid reasons to purge a token
        purgetype = [ 'InvalidGrantError', 'UnauthorizedClientError', 'InvalidClientError', 'InvalidTokenError' ]

        if result in purgetype:

            # purge the entry from the ldap user

            _ldaphelpers.update_singlevalue(dn, 'discordRefreshToken', None)
            _ldaphelpers.update_singlevalue(dn, 'discordAccessToken', None)
            _ldaphelpers.update_singlevalue(dn, 'discordAccessTokenExpires', None)

            msg = 'invalid discord token entries purged for user {}'.format(dn)
            logger.info(msg)

            return True

        # either way, this has failed in an unrecoverable way

        return True

    atoken = result.get('access_token')
    rtoken = result.get('refresh_token')
    expires = result.get('expires_at')

    # store the updated token
    result, value = storetokens(charid, atoken, rtoken, expires, token_type='discord')

    if result == False:
        msg = 'unable to store discord tokens for user {}'.format(dn)
        logger.error(msg)
        return False

    return True

def eve_tokenthings(dn, evetokens):

    logger = getlogger('maint.tokens.eve')

    charid = evetokens.get('uid')
    roles = evetokens.get('roles')
    ldap_scopes = evetokens.get('scopes')
    old_rtoken = evetokens.get('rtoken')

    if not old_rtoken:
        return True

    if roles is None:
        roles = []
    if ldap_scopes is None:
        ldap_scopes = []

    msg = 'updating eve token for charid {0}'.format(charid)
    logger.debug(msg)

    result, code = _everefresh.refresh_token(old_rtoken)

    if code is not True:
        # broken token, or broken oauth?
        # the distinction matters.
        # see env/lib/python3.5/site-packages/oauthlib/oauth2/rfc6749/errors.py

        msg = 'unable to refresh token for charid {0}: {1}'.format(charid, result)
        logger.error(msg)

        # only these exception types are valid reasons to purge a token
        purgetype = [ 'InvalidGrantError', 'UnauthorizedClientError', 'InvalidClientError', 'InvalidTokenError' ]

        if result in purgetype:

            # purge the entry from the ldap user

            _ldaphelpers.update_singlevalue(dn, 'esiRefreshToken', None)
            _ldaphelpers.update_singlevalue(dn, 'esiAccessToken', None)
            _ldaphelpers.update_singlevalue(dn, 'esiAccessTokenExpires', None)

            # corp roles and esi scopes now serve no purpose since the tokens are gone

            _ldaphelpers.update_singlevalue(dn, 'esiScope', None)
            _ldaphelpers.update_singlevalue(dn, 'corporationRole', None)

            msg = 'invalid token entries purged for user {}'.format(dn)
            logger.info(msg)

        # either way, this has failed in an unrecoverable way

        return True

    atoken = result.get('access_token')
    rtoken = result.get('refresh_token')
    expires = result.get('expires_at')

    # store the updated token
    result, value = storetokens(charid, atoken, rtoken, expires, token_type='esi')

    if result == False:
        msg = 'unable to store tokens for user {}'.format(dn)
        logger.error(msg)
        return False

    # the updated token is now in LDAP
    # fetch all corporation roles for the updated token if the scope allows that

    if 'esi-characters.read_corporation_roles.v1' in ldap_scopes:

        request_url = 'characters/{0}/roles/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v2')

        if code == 403:
            error = 'no perms to read roles for {0}: ({1}) {2}'.format(charid, code, result)
            logger.debug(error)
        elif not code == 200:
            error = 'unable to get character roles for {0}: ({1}) {2}'.format(charid, code, result)
            logger.error(error)

        else:

            # figure out what needs to be added and removed from ldap

            result = result.get('roles')

            missing_roles = set(result) - set(roles)
            extra_roles = set(roles) - set(result)

            for missing in list(missing_roles):
                _ldaphelpers.add_value(dn, 'corporationRole', missing)

            for extra in list(extra_roles):
                _ldaphelpers.update_singlevalue(dn, 'corporationRole', extra, delete=True)

    else:
            # legacy token that doesn't have this scope. probably not getting updates on these lol
        pass

    try:
        token_charid, charname, token_scopes = verify(atoken)
    except Exception as e:
        # this ought to never happen
        msg = 'unable to verify eve sso access token: {0}'.format(error)
        logger.error(msg)
        return

    if not token_charid == charid:
        # ought to never happen, just a safety check from a scare once
        msg = 'stored token for charid {0} belongs to charid {1}'.format(charid, token_charid)
        logger.critical(msg)
        return

    # so given an array of scopes, let's check that what we want is in the list of scopes the character's token has

    missing_scopes = set(token_scopes) - set(ldap_scopes)

    extra_scopes = set(ldap_scopes) - set(token_scopes)

    for missing in list(missing_scopes):
        _ldaphelpers.add_value(dn, 'esiScope', missing)

    for extra in list(extra_scopes):
        _ldaphelpers.update_singlevalue(dn, 'esiScope', extra, delete=True)

    return True
