from flask import Flask, request, url_for, json, Response
from tri_api import app
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import common.request_esi
import common.logger as _logger
from tri_core.common.testing import vg_alliances, vg_blues

@app.route('/core/<charid>/isblue', methods=['GET'])
def core_char_isblue(charid):

    # query ldap first


    userinfo = _ldaphelpers.ldap_userinfo(charid)

    # if ldap says you are blue, that is sufficient.

    if userinfo:

        if userinfo['accountStatus'] == 'blue':
            js = json.dumps( { 'code': 1 } )
        else:
            # not blue
            js = json.dumps( { 'code': 0 } )

        resp = Response(js, status=200, mimetype='application/json')
        return resp

    # test character
    code, result = test_char(charid)
    resp = Response(json.dumps(result), status=code, mimetype='application/json')
    return resp

def test_char(charid):

    import common.request_esi
    import common.logger as _logger

    # get character affiliations

    affilliations = _esihelpers.esi_affiliations(charid)
    allianceid = affilliations.get('allianceid')
    charname = affilliations.get('charname')
    corpid = affilliations.get('corpid')

    if not allianceid:
        # no alliance no blue
        result = { 'code': 0 }
        return 200, result

    # test the character's alliance
    code, result = test_alliance(allianceid)

    return code, result

def test_alliance(allianceid):

    import MySQLdb as mysql
    import common.credentials.database as _database
    import common.logger as _logger


    # hardcode handling for noobcorps
    if allianceid is 0 or None:
        result = { 'code': 0 }
        return 200, result

    # hard code for viral society alt alliance
    if allianceid == 99003916:
        result = { 'code': 1 }
        return 200, result

    # check against the blue list

    if allianceid in vg_blues() or allianceid in vg_alliances():

        # blue
        result = { 'code': 1 }
        return 200, result
    else:
        # not blue
        result  = { 'code': 0 }
        return 200, result

