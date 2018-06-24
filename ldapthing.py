import sys
from os import listdir
from os.path import isfile, join
from ldif import LDIFParser, LDIFRecordList
from tri_core.common.storetokens import storetokens

ldap_path = '/srv/api/ldap/'

onlyfiles = [f for f in listdir(ldap_path) if isfile(join(ldap_path, f))]

users = dict()

# collect all the old rtokens
for filename in onlyfiles:
    file = open(ldap_path + filename, 'rb')
    records = LDIFRecordList(file)
    records.parse()
    file.close()

    for dn, record in records.all_records:
        try:
#            rtoken = record['esiRefreshToken'][0].decode('utf-8')
            rtoken = record['discordRefreshToken'][0].decode('utf-8')
            charid = record['uid'][0].decode('utf-8')
        except Exception as e:
            continue
        users[charid] = rtoken

    print('closing file {0}'.format(filename))

# stuff all the rtokens into ldap

for charid in users:
    atoken = 'asdf'
    rtoken = users[charid]

    result, value = storetokens(charid, atoken, rtoken, token_type='discord')
    if result == False:
        print(value)
