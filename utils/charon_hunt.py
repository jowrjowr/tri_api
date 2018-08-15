from common.request_esi import esi
import common.request_esi
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers


def charon_hunt():


    dn = 'ou=People,dc=triumvirate,dc=rocks'
    filterstr = '(&(corporation=98203328)(esiAccessToken=*)(esiScope=esi-assets.read_assets.v1))'
    attributes = ['uid', 'characterName' ]
    code, users = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

    for dn in users:

        charname = users[dn]['characterName']
        charid = users[dn]['uid']

        print(charname, charid)

        request_url = 'characters/{0}/assets/'.format(charid)
        code, result = esi(__name__, request_url, version='v3', method='get', charid=charid)

        for item in result:
            if item['type_id'] == 20185:

                print(item)
                item_id = item['item_id']
                request_url = 'characters/{0}/assets/names/'.format(charid)
                data = '[{}]'.format(item_id)

                code, item_result = esi(__name__, request_url, data=data, version='v1', method='post', charid=charid)

                print(code, item_result)


charon_hunt()
