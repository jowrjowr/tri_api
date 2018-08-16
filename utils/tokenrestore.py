import sys
import ldap

from os import listdir
from os.path import isfile, join
from ldif import LDIFParser, LDIFRecordList
from tri_core.common.storetokens import storetokens
import common.credentials.ldap as _ldap

ldap_path = '/srv/api/ldap/'

onlyfiles = [f for f in listdir(ldap_path) if isfile(join(ldap_path, f))]

groups = dict()

# collect all the groups

for filename in onlyfiles:
    file = open(ldap_path + filename, 'rb')
    records = LDIFRecordList(file)
    records.parse()
    file.close()

    for dn, record in records.all_records:

        groups[dn] = []

        if not 'esiRefreshToken' in record:
            continue

        for authgroup in record['esiRefreshToken']:
            group = authgroup.decode('utf-8')
            groups[dn].append(group)
    print('closing file {0}'.format(filename))

for dn in groups.keys():

    # reconstruct the dn's list of authGroup attributes

    mod_attrs = []
    newgroups = []
    authgroups = groups[dn]

    for group in authgroups:
        group = str(group).encode('utf-8')
        newgroups.append(group)
    mod_attrs.append((ldap.MOD_REPLACE, 'esiRefreshToken', newgroups))

    ldap_conn = ldap.initialize(_ldap.ldap_host, bytes_mode=False)
    try:
        ldap_conn.simple_bind_s(_ldap.admin_dn, _ldap.admin_dn_password)
    except ldap.LDAPError as error:
        _logger.log('[' + __name__ + '] LDAP connection error: {}'.format(error),_logger.LogLevel.ERROR)
        sys.exit(1)

    try:
        result = ldap_conn.modify_s(dn, mod_attrs)
    except Exception as e:
        _logger.log('[' + __name__ + '] unable to update existing user {0} in ldap: {1}'.format(charid, e), _logger.LogLevel.ERROR)
        sys.exit(1)
