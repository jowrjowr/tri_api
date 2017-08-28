def audit_forums():

    import common.logger as _logger
    import common.credentials.database as _database
    import common.credentials.forums as _forumcreds
    import common.ldaphelpers as _ldaphelpers
    import common.request_esi
    from common.graphite import sendmetric
    from collections import defaultdict
    import json
    import urllib
    import html
    import MySQLdb as mysql
    import re

    import hashlib
    from passlib.hash import ldap_salted_sha1
    import uuid

    _logger.log('[' + __name__ + '] auditing forums',_logger.LogLevel.INFO)

    try:
        sql_conn_core = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    try:
        sql_conn_forum = mysql.connect(
            database=_forumcreds.mysql_db,
            user=_forumcreds.mysql_user,
            password=_forumcreds.mysql_pass,
            host=_forumcreds.mysql_host)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    # get everything from the permissions table

    cursor = sql_conn_core.cursor()
    query = 'SELECT allianceID,forum FROM Permissions'
    forum_mappings = dict()

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    finally:
        cursor.close()
        sql_conn_core.close()

    # this maps the alliance id to the primary forum group

    for row in rows:
        forum_mappings[row[0]] = row[1]

    # get all the forum users and stuff them into a dict for later processing

    cursor = sql_conn_forum.cursor()
    query = 'SELECT name, member_group_id, mgroup_others, ip_address, pp_main_photo, pp_thumb_photo FROM core_members'
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql forum error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    total_users = len(rows)
    _logger.log('[' + __name__ + '] forum users: {0}'.format(total_users), _logger.LogLevel.INFO)
    sendmetric(__name__, 'forums', 'statistics', 'total_users', total_users)

    users = dict()
    orphan = 0

    # special forum users that are not to be audited
    special = [ 'Admin', 'Sovereign' ]

    for charname, primary_group, secondary_string, last_ip,  pp_main_photo, pp_thumb_photo in rows:

        # dont work on these
        if charname in special:
            continue

        if charname == '' or charname == None:
            continue

        # recover user information
        users[charname] = dict()
        users[charname]['charname'] = charname
        users[charname]['doomheim'] = False
        users[charname]['primary'] = primary_group
        users[charname]['last_ip'] = last_ip
        users[charname]['pp_main_photo'] = pp_main_photo
        users[charname]['pp_thumb_photo'] = pp_thumb_photo

        # convert the comma separated list of groups to an array of integers

        secondaries = []
        for item in secondary_string.split(','):
            if not item == '' and not item == ' ':
                secondaries.append(int(item))
        users[charname]['secondary'] = secondaries

        cn = charname.replace(" ", '')
        cn = cn.replace("'", '')
        cn = cn.lower()

        # match up against ldap data
        dn = 'ou=People,dc=triumvirate,dc=rocks'
        filterstr='cn={0}'.format(cn)
        attributes = ['authGroup', 'accountStatus', 'uid', 'alliance', 'corporation' ]
        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)
        if code == False:
            _logger.log('[' + __name__ + '] ldap error: {0}'.format(result), _logger.LogLevel.ERROR)
            return

        if result == None:
            # nothing in ldap.
            # you WILL be dealt with later!
            orphan += 1
            users[charname]['charid'] = None
            users[charname]['alliance'] = None
            users[charname]['authgroups'] = []
            users[charname]['accountstatus'] = None
            users[charname]['corporation'] = None
        else:
            (dn, info), = result.items()

            alliance = info.get('alliance')
            corporation = info.get('corporation')

            if alliance is not None:
                alliance = int(alliance)
            if corporation is not None:
                corporation = int(corporation)

            users[charname]['alliance'] = alliance
            users[charname]['corporation'] = corporation

            users[charname]['charid'] = int( info['uid'] )
            users[charname]['accountstatus'] = info['accountStatus']
            users[charname]['authgroups'] = info['authGroup']

    # postprocessing

    _logger.log('[' + __name__ + '] forum users with no LDAP entry: {0}'.format(orphan),_logger.LogLevel.INFO)

    # map each user to a charID given that the username is exactly
    # a character name

    really_orphan = 0

    for charname in users:
        user = users[charname]
        primary = user['primary']

        if user['charid'] == None:
            # need to map the forum username to a character id
            query = { 'categories': 'character', 'datasource': 'tranquility', 'language': 'en-us', 'search': charname, 'strict': 'true' }
            query = urllib.parse.urlencode(query)
            esi_url = 'search/?' + query
            code, result = common.request_esi.esi(__name__, esi_url, 'get')
            _logger.log('[' + __name__ + '] /search output: {}'.format(result), _logger.LogLevel.DEBUG)

            if not code == 200:
                _logger.log('[' + __name__ + '] error searching for user {0}: {1}'.format(charname, result['error']),_logger.LogLevel.INFO)
                continue
            if len(result) == 0:
                really_orphan += 1
                users[charname]['doomheim'] = True
            if len(result) == 1:

                # make a stub ldap entry for them

                attributes = []
                attributes.append(('objectClass', ['top'.encode('utf-8'), 'pilot'.encode('utf-8'), 'simpleSecurityObject'.encode('utf-8'), 'organizationalPerson'.encode('utf-8')]))
                attributes.append(('characterName', [charname.encode('utf-8')]))
                attributes.append(('accountStatus', ['public'.encode('utf-8')]))
                attributes.append(('authGroup', ['public'.encode('utf-8')]))

                # cn, dn
                cn = charname.replace(" ", '')
                cn = cn.replace("'", '')
                cn = cn.lower()
                dn = "cn={},ou=People,dc=triumvirate,dc=rocks".format(cn)

                attributes.append(('sn',[cn.encode('utf-8')]))
                attributes.append(('cn',[cn.encode('utf-8')]))

                # character ID
                charid = result['character'][0]
                users[charname]['charid'] = charid
                attributes.append(('uid', [str(charid).encode('utf-8')]))

                # further affiliations will be handled by maintenance scripts

                # a random password keeps them from logging in but who cares

                password = uuid.uuid4().hex
                password_hash = ldap_salted_sha1.hash(password)
                password_hash = password_hash.encode('utf-8')
                attributes.append(('userPassword', [password_hash]))

                # create the ldap entry

                _ldaphelpers.ldap_adduser(dn, attributes)

    _logger.log('[' + __name__ + '] forum users who have biomassed: {0}'.format(really_orphan),_logger.LogLevel.INFO)

    # at this point every forum user has been mapped to their character id either via ldap or esi /search
    # work through each user and determine if they are correctly setup on the forums

    non_tri = 0
    for charname in users:

        charid = users[charname]['charid']

        if users[charname]['doomheim'] == True:
            forumpurge(charname)
            continue

        authgroups = users[charname]['authgroups']
        alliance = users[charname]['alliance']
        corporation = users[charname]['corporation']
        primary_group = users[charname]['primary']
        secondary_groups = users[charname]['secondary']
        forum_lastip = users[charname]['last_ip']

        if users[charname]['pp_main_photo'] is None:
        # set forum portrait to their in-game avatar if the user doesn't have one

            esi_url = 'characters/{0}/portrait/?datasource=tranquility'.format(charid)
            code, result = common.request_esi.esi(__name__, esi_url, 'get')
            _logger.log('[' + __name__ + '] /characters portrait output: {}'.format(result), _logger.LogLevel.DEBUG)

            if code == 200:

                portrait = result['px128x128']
                query = 'UPDATE core_members SET pp_main_photo=%s, pp_thumb_photo=%s, pp_photo_type="custom" WHERE name = %s'
                try:
                    cursor.execute(query, (portrait, portrait, charname,))
                    sql_conn_forum.commit()
                except Exception as err:
                    _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
                    return

            else:
                # something broke severely
                _logger.log('[' + __name__ + '] /characters portrait API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)


        ## start doing checks

        # only people in tri get anything other than public access on the tri forums
        # forum public/unprivileged groupid: 2

        vanguard = forum_mappings.keys()

        if alliance not in vanguard and primary_group != 2:

            # this char is not in a vanguard alliance but has non-public forum access
            print(charname, primary_group, alliance)
            print(type(alliance))
            forumpurge(charname)

            # log

            _logger.securitylog(__name__, 'forum demotion', charid=charid, charname=charname, ipaddress=forum_lastip)
            msg = 'non-vanguard character with privileged access demoted. charname: {0} ({1}), alliance: {2}, primary group: {3}, secondary group(s): {4}, last ip: {5}'.format(
                charname, charid, alliance, primary_group, secondary_groups, forum_lastip
            )
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
            non_tri += 1

        if alliance in vanguard:

            correct_primary = forum_mappings[alliance]
            correct_secondaries = []
            # construct the list of correct secondary groups

            for authgroup in authgroups:
                mapping = authgroup_map(authgroup)
                if not mapping == None:
                    correct_secondaries.append(mapping)

            # map any custom corp groups
            corpgroup = corp_map(corporation)
            if not corpgroup == None:
                correct_secondaries.append(corpgroup)

            ## deal with secondary groups

            # remove secondaries
            msg = 'char {0} current secondaries: {1} correct secondaries: {2}'.format(charname, secondary_groups, correct_secondaries)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)

            secondaries_to_remove = list( set(secondary_groups) - set(correct_secondaries) )

            # ips forum likes a comma separated list of secondaries
            if len(secondaries_to_remove) > 0:
                change = ''
                for group in correct_secondaries:
                    change = change + str(group) + ','
                change = change[:-1] # peel off trailing comma

                query = 'UPDATE core_members SET mgroup_others=%s WHERE name=%s'
                try:
                    cursor.execute(query, (change, charname,))
                    sql_conn_forum.commit()
                    msg = 'removed secondary group(s) {0} from {1}'.format(secondaries_to_remove, charname)
                    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)
                except Exception as err:
                    _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
                    return False

            secondaries_to_add = list( set(correct_secondaries) - set(secondary_groups) )

            # ips forum likes a comma separated list of secondaries
            if len(secondaries_to_add) > 0:
                change = ''
                for group in correct_secondaries:
                    change = change + str(group) + ','
                change = change[:-1] # peel off trailing comma

                query = 'UPDATE core_members SET mgroup_others=%s WHERE name=%s'
                try:
                    cursor.execute(query, (change, charname,))
                    sql_conn_forum.commit()
                    msg = 'added secondary group(s) {0} to {1}'.format(secondaries_to_add, charname)
                    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.INFO)
                except Exception as err:
                    _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
                    return False

            if not correct_primary == primary_group:
                query = 'UPDATE core_members SET member_group_id=%s WHERE name=%s'
                try:
                    cursor.execute(query, (correct_primary, charname,))
                    sql_conn_forum.commit()
                    _logger.log('[' + __name__ + '] adjusted primary forum group of {0} to {1}'.format(charname, correct_primary),_logger.LogLevel.INFO)
                except Exception as err:
                    _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
                    return False
    cursor.close()
    sql_conn_forum.close()
    _logger.log('[' + __name__ + '] non-vanguard forum users reset: {0}'.format(non_tri),_logger.LogLevel.INFO)

def forumpurge (charname):
    # remove their access

    import common.logger as _logger
    import common.credentials.forums as _forumcreds
    import MySQLdb as mysql

    try:
        sql_conn = mysql.connect(
            database=_forumcreds.mysql_db,
            user=_forumcreds.mysql_user,
            password=_forumcreds.mysql_pass,
            host=_forumcreds.mysql_host)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    cursor = sql_conn.cursor()

    # remove secondary groups
    # null not allowed: [commands.audit.forums] mysql error: (1048, "Column 'mgroup_others' cannot be null")

    query = 'UPDATE core_members SET mgroup_others=%s WHERE name=%s'
    try:
        cursor.execute(query, (' ', charname,))
    except Exception as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    # set them to the public group
    query = 'UPDATE core_members SET member_group_id=%s WHERE name=%s'
    try:
        cursor.execute(query, (2, charname,))
    except Exception as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    sql_conn.commit()
    cursor.close()
    return True

def authgroup_map(authgroup):

    # map ldap groups to forum secondary groups

    if authgroup == '500percent':       return 23
    if authgroup == 'command':          return 10
    if authgroup == 'trisupers':        return 13
    if authgroup == 'triprobers':       return 53
    if authgroup == 'dreads':           return 54
    if authgroup == 'vgsupers':         return 57
    if authgroup == 'skirmishfc':       return 11
    if authgroup == 'administration':   return 9
    if authgroup == 'skyteam':          return 12
    if authgroup == 'forumadmin':       return 4
    if authgroup == 'board':            return 67

    # public is group 2, but that's a primary group

    # no match

    return None

def corp_map(corpid):

    # map corps to forum secondary groups

    # avalanche
    if corpid == 98509794:        return 68
    # quam
    if corpid == 614700844:       return 69
    # NM
    if corpid == 1975749457:      return 70
    # SUPERFLUOUS WANDERLUST
    if corpid == 98144067:        return 71
    # Jenova Rising
    if corpid == 98226378:        return 72

    # no match

    return None
