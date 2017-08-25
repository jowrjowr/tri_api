import json
import common.request_esi
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import math

from tri_core.common.testing import vg_alliances

def audit_core():
    # keep the ldap account status entries in sync

    _logger.log('[' + __name__ + '] auditing CORE LDAP',_logger.LogLevel.INFO)

    vanguard = vg_alliances()

    if vanguard == False:
        return

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

    # bulk affiliations fetch

    data = []
    chunksize = 750 # current ESI max is 1000 but we'll be safe
    for user in users.keys():
        try:
            charid = int( users[user]['uid'] )
            data.append(charid)
        except Exception as error:
            pass
    length = len(data)
    chunks = math.ceil(length / chunksize)
    for i in range(0, chunks):
        chunk = data[:chunksize]
        del data[:chunksize]
        _logger.log('[' + __name__ + '] passing {0} items to affiliations endpoint'.format(len(chunk)), _logger.LogLevel.DEBUG)
        request_url = 'characters/affiliation/?datasource=tranquility'
        chunk = json.dumps(chunk)
        code, result = common.request_esi.esi(__name__, request_url, method='post', data=chunk, version='v1')
        print(code, result)

        for item in result:

            # locate the dn from the charid
            print(item)
            charid = item['character_id']
            for user in users.keys():
                try:
                    ldap_charid = int( users[user]['uid'] )
                except Exception as error:
                    ldap_charid = None

                if ldap_charid == charid:
                    dn = user

            users[dn]['esi_corp'] = item['corporation_id']
            if 'alliance_id' in item.keys():
                users[dn]['esi_alliance'] = item['alliance_id']
            else:
                users[dn]['esi_alliance'] = None

    # groups that a non-blue user is allowed to have

    safegroups = set([ 'public', 'ban_pending', 'banned' ])

    # loop through each user and determine the correct status

    for user in users.keys():
        dn = user

        if users[user]['uid'] == None:
            continue

        charid = int(users[user]['uid'])
        status = users[user]['accountStatus']
        charname = users[user]['characterName']
        raw_groups = users[user]['authGroup']


        # ESI current
        esi_allianceid = users[user].get('esi_alliance')
        if esi_allianceid is False:
            continue
        elif esi_allianceid is not None:
            alliance_info = _esihelpers.alliance_info(esi_allianceid)
            esi_alliancename = alliance_info.get('alliance_name')
        else:
            esi_alliancename = None

        esi_corpid = users[user].get('esi_corp')
        if esi_corpid is False:
            continue
        elif esi_corpid is not None:
            corporation_info = _esihelpers.corporation_info(esi_corpid)
            esi_corpname = corporation_info.get('corporation_name')
        else:
            # most likely doomheim, so treating as such.
            esi_corpid = 1000001
            esi_corpname = 'Doomheim'


        # what ldap thinks

        try:
            ldap_allianceid = int(users[user].get('alliance'))
        except Exception as e:
            ldap_allianceid = None
        try:
            ldap_corpid = int(users[user].get('corporation'))
        except Exception as e:
            ldap_corpid = None

        ldap_alliancename = users[user].get('allianceName')
        ldap_corpname = users[user].get('corporationName')

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

