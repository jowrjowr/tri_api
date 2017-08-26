import json
import common.request_esi
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import math
import resource
from concurrent.futures import ThreadPoolExecutor, as_completed

from tri_core.common.testing import vg_alliances

def audit_core():
    # keep the ldap account status entries in sync

    _logger.log('[' + __name__ + '] auditing CORE LDAP',_logger.LogLevel.INFO)


    # fix open file limitations

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (25000, 75000))
    except Exception as e:
        pass

    # fetch all non-banned LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(!(accountstatus=banned))(!(accountStatus=immortal)))'
    attributes = ['uid']
    code, nonbanned_users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return

    # fetch all tri LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'alliance=933731581'
    attributes = ['uid' ]
    code, tri_users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return

    # fetch all blue

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = 'accountStatus=blue'
    attributes = ['uid']
    code, blue_users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return

    # fetch ALL LDAP users

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(!(accountStatus=immortal))'
    attributes = ['uid', 'characterName', 'accountStatus', 'authGroup', 'corporation', 'alliance', 'allianceName', 'corporationName' ]
    code, users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    if code == False:
        return

    _logger.log('[' + __name__ + '] total ldap users: {}'.format(len(users)),_logger.LogLevel.INFO)
    _logger.log('[' + __name__ + '] total non-banned ldap users: {}'.format(len(nonbanned_users)),_logger.LogLevel.INFO)
    _logger.log('[' + __name__ + '] total blue ldap users: {}'.format(len(blue_users)),_logger.LogLevel.INFO)
    _logger.log('[' + __name__ + '] total tri ldap users: {}'.format(len(tri_users)),_logger.LogLevel.INFO)



    # loop through each user and determine the correct status

    activity = dict()

    with ThreadPoolExecutor(50) as executor:
        futures = { executor.submit(user_audit, dn, users[dn]): dn for dn in users.keys() }
        for future in as_completed(futures):
            data = future.result()
            activity[dn] = data
    print(activity)

def user_audit(dn, details):

    msg = 'auditing user: {0}'.format(dn)
    _logger.log('[' + __name__ + '] {0}'.format(msg),_logger.LogLevel.DEBUG)
    # groups that a non-blue user is allowed to have

    safegroups = set([ 'public', 'ban_pending', 'banned' ])

    if details['uid'] == None:
        return False

    charid = int(details['uid'])
    status = details['accountStatus']
    charname = details['characterName']
    raw_groups = details['authGroup']

    # affiliations information
    # ESI current

    request_url = 'characters/{0}/?datasource=tranquility'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v4')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get character info for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return False

    esi_corpid = result.get('corporation_id')

    # alliance id, if any
    request_url = 'corporations/{0}/?datasource=tranquility'.format(esi_corpid)
    code, result = common.request_esi.esi(__name__, request_url, method='get', version='v3')
    if not code == 200:
        _logger.log('[' + __name__ + '] unable to get character info for {0}: {1}'.format(charid, error),_logger.LogLevel.ERROR)
        return False

    esi_allianceid = result.get('alliance_id')

    if esi_allianceid is not None:
        alliance_info = _esihelpers.alliance_info(esi_allianceid)
        esi_alliancename = alliance_info.get('alliance_name')
    else:
        esi_alliancename = None

    if esi_corpid is not None:
        corporation_info = _esihelpers.corporation_info(esi_corpid)
        esi_corpname = corporation_info.get('corporation_name')
    else:
        # most likely doomheim, so treating as such.
        esi_corpid = 1000001
        esi_corpname = 'Doomheim'

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

    vanguard = vg_alliances()

    if vanguard == False:
        return

    # NOT banned:

    if 'banned' not in raw_groups and status is not 'banned':
        if esi_allianceid in vanguard and 'vanguard' not in eff_groups:
            # oops. time to fix you.
            # you'll get more privileges on the next go-round
            _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'blue')


        if not esi_allianceid in vanguard:
            # reset authgroups and account status

            if not status == 'public':
                _ldaphelpers.update_singlevalue(dn, 'accountStatus', 'public')

            if len(eff_groups) > 0:
                _ldaphelpers.purge_authgroups(dn, eff_groups)

        if status == 'blue':

            triumvirate = 933731581

            if esi_allianceid == triumvirate and 'triumvirate' not in eff_groups:
                # all non-banned tri get trimvirate
                _ldaphelpers.add_value(dn, 'authGroup', 'triumvirate')

            if 'vanguard' not in eff_groups:
                # all non-banned blue get vanguard
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
