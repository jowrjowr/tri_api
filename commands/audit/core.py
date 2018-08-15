import json
import common.request_esi
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import math
import time
import resource
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from tri_core.common.testing import vg_alliances, vg_blues, vg_renters
from common.logger import getlogger_new as getlogger

def audit_core():
    # keep the ldap account status entries in sync

    logger = getlogger('audit.core')
    logger.info('auditing CORE LDAP')
    # fix open file limitations

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (25000, 75000))
    except Exception as e:
        logger.warn('unable to set nofile rlimit: {0}'.format(e))
        pass

    # fetch all non-banned LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(!(accountstatus=banned))(!(accountStatus=immortal)))'
    attributes = ['uid']
    code, nonbanned_users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        logger.error('unable to find ldap users')
        return

    # fetch all tri LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'alliance=933731581'
    attributes = ['uid' ]
    code, tri_users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        logger.error('unable to find ldap users')
        return

    # fetch all blue

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'accountStatus=blue'
    attributes = ['uid']
    code, blue_users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        logger.error('unable to find ldap users')
        return

    # fetch ALL LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(!(accountStatus=immortal))'
    attributes = ['uid', 'characterName', 'accountStatus', 'authGroup', 'corporation',
        'alliance', 'allianceName', 'corporationName', 'discordRefreshToken', 'discorduid',
        'discord2fa', 'discordName', 'altOf', 'esiRefreshToken', 'esiScope', 'lastLogin',
        'corporationRole'
    ]

    code, users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        logger.error('unable to find ldap users')
        return

    logger.info('total ldap users: {}'.format(len(users)))
    logger.info('total non-banned ldap users: {}'.format(len(nonbanned_users)))
    logger.info('total blue ldap users: {}'.format(len(blue_users)))
    logger.info('total tri ldap users: {}'.format(len(tri_users)))


    # loop through each user and determine the correct status

    activity = dict()

    with ThreadPoolExecutor(30) as executor:
        futures = { executor.submit(user_audit, dn, users[dn]): dn for dn in users.keys() }
        for future in as_completed(futures):
            data = future.result()
            activity[dn] = data

def purge(dn, details):

    # start going through and determine whether the ldap entry needs to be removed
    # no need to keep affiliation info on basically stub entries

    return False

    logger = logging.getLogger('audit.core.user.purge')

    status = details['accountStatus']
    authgroups = details['authGroup']
    esi_rtoken = details['esiRefreshToken']
    discord_rtoken = details['discordRefreshToken']
    discorduid = details['discorduid']
    altof = details['altOf']

    # only look at people with no access or special significance
    if status != 'public' and authgroups != [ 'public' ]:
        return False

    # dont punt registered alts
    if altof:
        return False

    # dont purge stuff we have tokens for
    if esi_rtoken or discord_rtoken:
        return False

    # dont purge people who we have a discord uid to tie to

    if discorduid:
        return False

    logger.info('purging {0} from ldap'.format(dn))
    _ldaphelpers.purge_dn(dn)
    return True

def user_audit(dn, details):

    if dn == 'ou=People,dc=triumvirate,dc=rocks':
        return

    logger = logging.getLogger('audit.core.user')

    msg = 'auditing user: {0}'.format(dn)
    logger.debug(msg)

    # groups that a non-blue user is allowed to have

    safegroups = set([ 'public', 'ban_pending', 'banned', ])

    if details['uid'] == None:
        logger.error('dn {0} has no charid'.format(dn))
        return False

    charid = int(details['uid'])
    status = details['accountStatus']
    altof = details['altOf']
    charname = details['characterName']
    raw_groups = details['authGroup']
    esi_rtoken = details['esiRefreshToken']
    discord_rtoken = details['discordRefreshToken']
    ldap_discorduid = details['discorduid']
    ldap_discord2fa = details['discord2fa']
    ldap_discordname = details['discordName']
    ldap_scopes = details['esiScope']
    ldap_roles = details['corporationRole']

    if ldap_scopes is None:
        ldap_scopes = []
    if ldap_roles is None:
        ldap_roles = []

    if details['lastLogin'] is not None:
        ldap_lastlogin = float(details['lastLogin'])
    else:
        ldap_lastlogin = 0

    # we do not need to keep entries on people where there's no meaningful data

    purged = purge(dn, details)

    if purged:
        # this has been purged, we're done here.
        msg = 'successfully purged dn {0}'.format(dn)
        logger.debug(msg)
        return

    ## bugfix sanity checks
    # there was once a bug where people would be marked as alts of themselves
    # this results in interesting effects

    if altof == charid:
        _ldaphelpers.update_singlevalue(dn, 'altOf', None)

    # there was once a time where tokens were purged but their associated scopes and roles were not

    if esi_rtoken is None:

        if ldap_scopes != []:
            _ldaphelpers.update_singlevalue(dn, 'esiScope', None)
        if ldap_roles != []:
            _ldaphelpers.update_singlevalue(dn, 'corporationRole', None)

    # discord
    # this seems like the best place to put this logic

    if details['discordRefreshToken'] is not None:
        request_url = '/users/@me'
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v6', base='discord')

        if not code == 200:
            msg = 'unable to get discord user information for {0}: ({1}) {2}'.format(dn, code, result)
            logger.error(msg)
            return False

        discorduid = int(result.get('id'))
        discord2fa = result.get('mfa_enabled')
        discordname = result.get('username')

        # update/set discord UID and username
        if ldap_discorduid is None:
            _ldaphelpers.add_value(dn, 'discorduid', discorduid)
        elif ldap_discorduid != discorduid:
            _ldaphelpers.update_singlevalue(dn, 'discorduid', discorduid)

        if ldap_discordname is None:
            _ldaphelpers.add_value(dn, 'discordName', discordname)
        elif ldap_discordname != discordname:
            _ldaphelpers.update_singlevalue(dn, 'discordName', discordname)

        # update 2fa status

        if ldap_discord2fa is None:
            _ldaphelpers.add_value(dn, 'discord2fa', discord2fa)
        elif ldap_discord2fa != discord2fa:
            _ldaphelpers.update_singlevalue(dn, 'discord2fa', discord2fa)

    if details['esiRefreshToken'] is not None and 'esi-location.read_online.v1' in ldap_scopes:
        # get online status if possible

        request_url = 'characters/{0}/online/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, method='get', charid=charid, version='v2')

        if not code == 200:
            # it doesn't really matter
            msg = 'characters online API error {0}: {1}'.format(code, result)
            logger.error(msg)
        else:
            # example:
            # {'online': False, 'last_login': '2017-07-11T06:38:19Z', 'last_logout': '2017-07-11T06:32:41Z', 'logins': 2474}
            last_login = time.strptime(result.get('last_login'), "%Y-%m-%dT%H:%M:%SZ")
            last_login = time.mktime(last_login)

            if ldap_lastlogin != last_login:
                _ldaphelpers.update_singlevalue(dn, 'lastLogin', last_login)
                ldap_lastlogin = last_login
    else:
        # so there's always a valid comparison
        if ldap_lastlogin != 0:
            _ldaphelpers.update_singlevalue(dn, 'lastLogin', 0)

    # affiliations information

    affilliations = _esihelpers.esi_affiliations(charid)

    if affilliations.get('error'):
        return False

    esi_allianceid = affilliations.get('allianceid')
    esi_alliancename = affilliations.get('alliancename')
    esi_corpid = affilliations.get('corpid')
    esi_corpname = affilliations.get('corpname')

    # what ldap thinks

    try:
        ldap_allianceid = int(details.get('alliance'))
    except Exception as e:
        ldap_allianceid = None
    try:
        ldap_corpid = int(details.get('corporation'))
    except Exception as e:
        ldap_corpid = None

    ldap_alliancename = details.get('allianceName')
    ldap_corpname = details.get('corporationName')

    # user's effective managable groups
    eff_groups = list( set(raw_groups) - safegroups )

    # tinker with ldap to account for reality

    if not esi_allianceid == ldap_allianceid:
        # update a changed alliance id
        _ldaphelpers.update_singlevalue(dn, 'alliance', str(esi_allianceid))

    if not esi_alliancename == ldap_alliancename:
        # update a changed alliance name
        _ldaphelpers.update_singlevalue(dn, 'allianceName', str(esi_alliancename))

    if not esi_corpid == ldap_corpid:
        # update a changed corp id
        _ldaphelpers.update_singlevalue(dn, 'corporation', str(esi_corpid))
    if not esi_corpname == ldap_corpname:
        # update a changed corp name
        _ldaphelpers.update_singlevalue(dn, 'corporationName', str(esi_corpname))

    # GROUP MADNESS

    vanguard = vg_alliances() + vg_blues()

    if vanguard == False:
        return

    # NOT banned:

    if 'banned' not in raw_groups and status is not 'banned':

        # non-banned people should all have public
        # not sure how this happens

        if 'public' not in raw_groups:
            _ldaphelpers.add_value(dn, 'authGroup', 'public')

        # this character is blue but not marked as such
        if esi_allianceid in vg_alliances() or esi_allianceid in vg_blues() or esi_allianceid in vg_renters():
            if not status == 'blue':
                _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'blue')

        # pubbies do not need status. this does not affect alts meaningfully.
        if not esi_allianceid in vg_alliances() and esi_allianceid not in vg_blues() and esi_allianceid not in vg_renters():

            if not status == 'public':
                _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'public')

            if len(eff_groups) > 0:
                _ldaphelpers.purge_authgroups(dn, eff_groups)

        triumvirate = 933731581

        # activity purge

        if ldap_lastlogin is None:
            ldap_lastlogin = 0

        login_difference = time.time() - ldap_lastlogin

        if login_difference > 30*86400 and esi_allianceid == triumvirate:
            # logic to purge out of groups based on inactivity
            pass
#            _ldaphelpers.purge_authgroups(dn, eff_groups)
#            return

        # some checks for those marked blue already
        if status == 'blue':

            if 'vanguard' in eff_groups and esi_allianceid in vg_blues():
                # a special case for people moving from vanguard to vg blues
                _ldaphelpers.purge_authgroups(dn, ['vanguard'])

            if 'vanguardBlue' in eff_groups and esi_allianceid in vg_alliances():
                # a special case for people moving from vanguard blues to vanguard
                _ldaphelpers.purge_authgroups(dn, ['vanguardBlue'])

            if 'renters' not in eff_groups:
                if esi_allianceid in vg_renters():
                    # renters get renters
                    _ldaphelpers.add_value(dn, 'authGroup', 'renters')

            if 'triumvirate' not in eff_groups:
                if esi_allianceid == triumvirate:
                    # tri get trimvirate
                    _ldaphelpers.add_value(dn, 'authGroup', 'triumvirate')

            if 'vanguardBlue' not in eff_groups:
                if esi_allianceid in vg_blues():
                    # vanguard blues get this
                    _ldaphelpers.add_value(dn, 'authGroup', 'vanguardBlue')

            if 'vanguard' not in eff_groups:
                if esi_allianceid in vg_alliances():
                    # vanguard alliances get vanguard
                    _ldaphelpers.add_value(dn, 'authGroup', 'vanguard')

    # purge shit from banned people

    if 'banned' in raw_groups:

        # purge off any groups you shouldn't have

        if len(eff_groups) > 0:
            _ldaphelpers.purge_authgroups(dn, eff_groups)

        if not status == 'banned':
            _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'banned')

    if status == 'banned' and 'banned' not in raw_groups:
        # this shouldn't happen but this makes sure data stays synchronized

        # purge off any groups you shouldn't have
        if len(eff_groups) > 0:
            _ldaphelpers.purge_authgroups(dn, eff_groups)
    return True
