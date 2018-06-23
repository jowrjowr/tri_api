from common.logger import getlogger_new as getlogger
import common.logger as _logger
import common.esihelpers as _esihelpers
import common.credentials.database as _database
import common.credentials.ldap as _ldap
import common.request_esi
from common.graphite import sendmetric
import ldap
import json
import datetime
import uuid
import time
import logging
from datetime import datetime
from passlib.hash import ldap_salted_sha1

def registeruser(charid, atoken, rtoken, isalt=False, altof=None, tempblue=False, renter=False):
    # put the barest skeleton of information into ldap/mysql

    # get character affiliations

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    if isalt:
        msg = 'registering user {0} (alt of {1})'.format(charid, altof)
        logging.info(msg)

    else:
        msg = 'registering user {}'.format(charid)
        logging.info(msg)

    # affiliations

    affiliations = _esihelpers.esi_affiliations(charid)
    charname = affiliations.get('charname')
    corpid = affiliations.get('corpid')
    corpname = affiliations.get('corporation_name')
    allianceid = affiliations.get('allianceid')
    alliancename = affiliations.get('alliancename')

    # sort out basic auth groups

    if tempblue:
        # default level of access for vanguard blues
        authgroups = [ 'public', 'vanguardBlue' ]
    if renter:
        # renter groups
        authgroups = [ 'public', 'renters' ]
    else:
        # default level of access
        authgroups = [ 'public' ]

    if 'allianceid' in user.keys():
        if user['allianceid'] == 933731581:
            # tri specific authgroup
            authgroups.append('triumvirate')

    # setup the service user/pass

    cn, dn = _ldaphelpers.ldap_normalize_charname(charname)
    dn = "cn={},ou=People,dc=triumvirate,dc=rocks".format(cn)

    # create the stub

    result, code = _ldaphelpers.create_stub_user(
        charid=charid,
        charname=charname,
        isalt=isalt,
        altof=altof,
        accountstatus='blue',
        authgroups=authgroups,
        rtoken=rtoken,
        atoken=atoken
    )

    if result:

        if isalt:
            msg = 'new user {0} (alt of {1} registered'.format(charname, altof)
        else:
            msg = 'new user {0} registered'.format(charname)

        logger.info(msg)
        return True
    else:
        msg = 'unable to register user {0}: {1}'.format(charname, error)
        return False

