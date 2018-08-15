import copy
import json
import common.ldaphelpers as _ldaphelpers
import common.database as _database
import common.request_esi
import requests
import MySQLdb as mysql
import math
import uuid
import hashlib

from datetime import datetime

def migrateusers():

    try:
        sql_conn = mysql.connect(
            database='blacklist',
            user='root',
            password='lskdjflaksdjflaksjdf',
            host=_database.DB_HOST)
    except mysql.Error as err:
        print(err)
        return False

    cursor = sql_conn.cursor()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    print('reeee')
    # each user will have a dictionary entry
    users = dict()
    # existing users

    # old assed blacklist
    query = 'SELECT blDate,blCharID,blMainID from bl'
    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        print('err')
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
        print('err')
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

        for item in user.keys():
            if isinstance(user[item], bytes):
                user[item] = user[item].decode('utf-8')

        approvedby = user['approvedby']
        if approvedby is None:
            approvedby = 118869737
            user['approvedby'] = 118869737

        try:
            request_url = 'characters/{0}/'.format(approvedby)
            code, result = common.request_esi.esi(__name__, request_url, 'get', version='v4')
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
        request_url = 'https://esi.evetech.net/latest/characters/affiliation/'
        chunk = json.dumps(chunk)
        result = requests.post(request_url, headers=headers, data=chunk)
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

        request_url = 'characters/{0}/'.format(charid)
        code, result = common.request_esi.esi(__name__, request_url, 'get', version='v4')
        if code == 200:
            user['charname'] = result['name']
        else:
            print(code, result)

        # sort out scoping/authgroups
        # account status is one of the following:
        # public (pubbie access or lack thereof), banned, blue
        # privileges delinated with authgroups

        user['accountstatus'] = 'public'

        authgroups = []

        # banned and confirmed
        if 'blconfirmdate' in user.keys():
            authgroups.append('banned')
            user['accountstatus'] = 'banned'
        # banned but not confirmed
        if 'bldate' in user.keys() and not 'blconfirmdate' in user.keys():
            authgroups.append('ban_pending')
            authgroups.append('public')

        user['authgroups'] = authgroups
        users[charid] = user

    sql_conn.close()

    for charid in users.keys():

        data = users[charid]

        dn = 'ou=People,dc=triumvirate,dc=rocks'
        filterstr='uid={}'.format(charid)
        attrlist=['characterName', 'accountStatus', 'authGroup' ]
        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

        if code == False:
            msg = 'unable to fetch ldap information: {}'.format(error)
            print(msg)
            return

        if result is not None:
            # fix the bytefucked reasontext

            (dn, info), = result.items()

            if info['accountStatus'] == 'blue':
                print(info)
                print(users[charid])
                continue
            else:
                _ldaphelpers.purge_dn(dn)

        # build new entry

        charname = data['charname']
        accountstatus = data['accountstatus']
        authgroups = data['authgroups']
        banreason = ban_convert(data.get('reasontype'))
        altof = data.get('altof')

        cn, dn = _ldaphelpers.ldap_normalize_charname(data['charname'])
        _ldaphelpers.ldap_create_stub(charid=charid, authgroups=authgroups, altof=altof, accountstatus=accountstatus, charname=charname)

        _ldaphelpers.add_value(dn, 'banReason', banreason)
        _ldaphelpers.add_value(dn, 'banDescription', data.get('reasontext'))
        _ldaphelpers.add_value(dn, 'banReportedBy', data.get('requestedby'))
        _ldaphelpers.add_value(dn, 'banDate', data.get('bldate'))

        if 'banned' in authgroups:
            _ldaphelpers.add_value(dn, 'banApprovedBy', data['approvedby'])
            _ldaphelpers.add_value(dn, 'banApprovedOn', data['blconfirmdate'])

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

if __name__ == "__main__":
    migrateusers()
