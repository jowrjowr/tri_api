import copy
import json
import ldap
import ldap.modlist as modlist
import common.database as _database
import common.logger as _logger
import common.request_esi
import requests
import MySQLdb as mysql
import math
import phpserialize
import uuid
import hashlib

from datetime import datetime
from passlib.hash import ldap_salted_sha1

#dostuff = _jabber.setup(90622096, True)
#print(dostuff)

def migrateusers():

    try:
        sql_conn = mysql.connect(
            database='blacklist',
            user='root',
            password='wua8e0.NR68qI',
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    cursor = sql_conn.cursor()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    # each user will have a dictionary entry
    users = dict()
    # existing users

    # Users table
    query = 'SELECT charID, ServicePassword, MainCharID FROM core.Users'
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    print("users table count: {}".format(rowcount))

    for row in rows:
        charid = row[0]
        if charid in users:
            user = users[charid]
        else:
            user = dict()

        user['charid'], user['password'], user['altof'] = row
        for item in list(user):
            if user[item] == None:
                user.pop(item, None)
        users[charid] = user

    # bans last to clobber active users "just in case"

    # old assed blacklist
    query = 'SELECT blDate,blCharID,blMainID from bl'
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    print("old blacklist table count: {}".format(rowcount))
    # old blacklist table
    for row in rows:



        bldate, charid, altof = row

        if charid in users:
            user = users[charid]
        else:
            user = dict()

        user['altof'] = altof
        user['charid'] = charid
        user['accountstatus'] = 'banned'
        user['authgroup'] = 'banned'
        user['approvedby'] = 118869737
        user['requestedby'] = 118869737
        user['reasontype'] = 'legacy'
        user['reasontext'] = 'legacy detail-free blacklist'

        # format ban date to epoch

        bldate = str(bldate)
        bldate = datetime.strptime(bldate, '%Y-%m-%d').timestamp()
        user['bldate'] = bldate
        user['blconfirmdate'] = bldate

        # store away
        for item in list(user):
            if user[item] == None or user[item] == '':
                user.pop(item, None)
        users[charid] = user

    # new blacklist

    query = 'SELECT UNIX_TIMESTAMP(entryDate), UNIX_TIMESTAMP(confirmDate), requestedByCharID, charID, approvedByCharID, reasonType, reasonText, mainCharID FROM Blacklist'
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    print("blacklist table count: {}".format(rowcount))
    # new blacklist table
    for row in rows:


        charid = row[3]

        if charid in users:
            user = users[charid]
        else:
            user = dict()

        user['bldate'], user['blconfirmdate'], user['requestedby'], user['charid'], user['approvedby'], user['reasontype'], user['reasontext'], user['altof'] = row

        try:
            request_url = 'https://esi.tech.ccp.is/latest/characters/{0}/'.format(user['approvedby'])
            code, result = common.request_esi.esi(__name__, request_url, 'get')
            user['approvedbyname'] = result['name']
        except Exception as error:
            user['approvedbyname'] = 'Unknown'

        for item in list(user):
            if user[item] == None or user[item] == '':
                user.pop(item, None)
        users[charid] = user


    # sort common stuff

    # character affiliations in bulk
    data = []
    chunksize = 750
    for charid in users.keys():
        data.append(charid)
    length = len(data)
    chunks = math.ceil(length / chunksize)
    for i in range(0, chunks):
        chunk = data[:chunksize]
        del data[:chunksize]
        print('passing {} items'.format(len(chunk)))
        request_url = 'https://esi.tech.ccp.is/latest/characters/affiliation/'
        chunk = json.dumps(chunk)
        result = requests.post(request_url, headers=headers, data=chunk)
        print(result.text)
        for item in result.json():
            charid = item['character_id']
            users[charid]['corpid'] = item['corporation_id']
            if 'alliance_id' in item.keys():
                users[charid]['allianceid'] = item['alliance_id']
            else:
                users[charid]['allianceid'] = None

    for charid in users.keys():

        user = users[charid]

        # character name

        request_url = 'https://esi.tech.ccp.is/latest/characters/{0}/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, 'get')
        user['charname'] = result['name']

        # sort out scoping/authgroups
        # account status is one of the following:
        # public (pubbie access or lack thereof), banned, blue
        # privileges delinated with authgroups

        user['accountstatus'] = 'blue'

        authgroups = ['public', 'vanguard'] # default level of access for blues

        if 'allianceid' in user.keys():
            if user['allianceid'] == 933731581:
                # tri specific authgroup
                authgroups.append('triumvirate')
        user['authgroup'] = authgroups
        # banned and confirmed
        if 'blconfirmdate' in user.keys():
            user['authgroup'] = [ 'banned' ]
            user['accountstatus'] = 'banned'
        # banned but not confirmed
        if 'bldate' in user.keys() and not 'blconfirmdate' in user.keys():
            user['authgroup'] = [ 'ban_pending' ]
            user['accountstatus'] = 'public'

        users[charid] = user

    # groups
    query = 'SELECT jabber,Members from core.Groups WHERE idGroups < 10'
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False

    print("groups count: {}".format(rowcount))
    for row in rows:
        group, members = row
        members = phpserialize.loads(members)
        for key in members:
            charid = int(members[key].decode('utf-8'))
            try:
                users[charid]['authgroup'].append(group)
            except Exception as error:
                print('unable to add group {0} to user {1}'.format(group,charid))
    print("distinct ldap users: {}".format(len(users.keys())))
    # loop through the user dict and store the user

    ldap_conn = ldap.initialize('ldap://localhost:389', bytes_mode=False)
    ldap_conn.simple_bind_s('cn=admin,dc=triumvirate,dc=rocks','blahblahFUCKER!')
    for charid in users.keys():

        user = users[charid]
        #print("uid: " + str(charid))
        cn = str(user['charname']).replace(" ", '')
        cn = cn.replace("'", '')
        cn = cn.lower()
        dn = "cn={},ou=People,dc=triumvirate,dc=rocks".format(cn)
        user['cn'] = cn

        # encode all this shit to bytes
        for item in user.keys():
            if not item == 'authgroup':
                user[item] = str(user[item]).encode('utf-8')
            else:
                groups = user['authgroup']
                newgroups = []
                for group in groups:
                    group = str(group).encode('utf-8')
                    newgroups.append(group)
                user['authgroup'] = newgroups

            attrs = []
            attrs.append(('objectClass', ['top'.encode('utf-8'), 'pilot'.encode('utf-8'), 'simpleSecurityObject'.encode('utf-8'), 'organizationalPerson'.encode('utf-8')]))
            attrs.append(('sn', [user['cn']]))
            attrs.append(('cn', [user['cn']]))
            attrs.append(('uid', [user['charid']]))
            attrs.append(('characterName', [user['charname']]))
            attrs.append(('accountStatus', [user['accountstatus']]))
            attrs.append(('authGroup', user['authgroup']))

            if 'password' in user.keys():
                # existing password
                try:
                    password = user['password'].decode('utf-8')
                except Exception as error:
                    password = user['password']
            else:
                # no password? you get a random one
                password = uuid.uuid4().hex

            password_hash = ldap_salted_sha1.hash(password)
            #print('user: {0}, password: {1}, hash: {2}'.format(cn, str(password), password_hash))
            password_hash = password_hash.encode('utf-8')
            attrs.append(('userPassword', [password_hash]))

            # add normal shit
            if 'allianceid' in user.keys():
                attrs.append(('alliance', [user['allianceid']]))
            if 'corpid' in user.keys():
                attrs.append(('corporation', [user['corpid']]))

            if 'ts_uid' in user.keys():
                attrs.append(('teamspeakuid', [user['ts_uid']]))
            if 'ts_dbid' in user.keys():
                attrs.append(('teamspeakdbid', [user['ts_dbid']]))

            # add ban

            # confirmed ban
            if 'blconfirmdate' in user.keys():
                attrs.append(('banApprovedBy', [user['approvedby']]))
                attrs.append(('banApprovedOn', [user['blconfirmdate']]))

            # normal ban data
            if 'bldate' in user.keys():
                attrs.append(('banDate', [user['bldate']]))
            if 'reasontype' in user.keys():
                attrs.append(('banReason', [user['reasontype']]))
            if 'requestedby' in user.keys():
                attrs.append(('banReportedBy', [user['requestedby']]))
            if 'reasontext' in user.keys():
                attrs.append(('banDescription', [user['reasontext']]))

            # tag the alts
            if 'altof' in user.keys():
                attrs.append(('altOf', [user['altof']]))

        try:
            result = ldap_conn.search_s('ou=People,dc=triumvirate,dc=rocks', ldap.SCOPE_SUBTREE, "(uid={})".format(charid))
            result_count = result.__len__()
        except Exception as error:
            pass
            # not sure how to handle errors yet lol

        # build the modifivation version of attributes
        mod_attrs = []
        for tuple in attrs:
            mod_attrs.append( (ldap.MOD_REPLACE,) + tuple )

        if result_count == 0:
            print('adding {0}'.format(user['charname']))
            # no existing entry. create a new one.

            try:
                # will get a 105 in the result as per
                # https://access.redhat.com/documentation/en-US/Red_Hat_Directory_Server/8.0/html/Configuration_and_Command_Reference/Configuration_Command_File_Reference-Access_Log_and_Connection_Code_Reference.html
                result = ldap_conn.add_s(dn, attrs)
            except TypeError as e:
                print('typeerror: ' + str(e))
            except Exception as e:
                print(attrs)
                error = list(e.args)[0]
                err_desc = error['desc']
                if 'info' in error:
                    err_info = error['info']
                    print('you fucked up. {0}: {1}'.format(err_desc, err_info))
                else:
                    print('you fucked up. {0}'.format(err_desc))
        else:
            # already an existing entry. update it?

            try:
                print('modifying dn: {}'.format(dn))
                result = ldap_conn.modify_s(dn, mod_attrs)
            except ldap.LDAPError as error:
                _logger.log('[' + __name__ + '] unable to update group {0} memberlist: {1}'.format(group,error),_logger.LogLevel.ERROR)

    sql_conn.close()


migrateusers()
