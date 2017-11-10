#!/usr/bin/python3

import sleekxmpp
import xmltodict
import common.logger as _logger
from common.discord_api import discord_forward

def jid_ping(self, jid):

    # XEP 0199 - pinging a jid

    jid_short, detail= jid.split('/')

    # ping

    try:
        result = self['xep_0199'].ping(
            jid = jid,
            timeout = 2,
            ifrom = self.boundjid,
        )
    except sleekxmpp.exceptions.IqTimeout as error:
        # maybe setup a retry loop? idk
        _logger.log('[' + __name__ + '] timeout pinging {0}'.format(jid_short),_logger.LogLevel.WARNING)
        print('ERRRROR')
        return None

    return result

class Jabber(sleekxmpp.ClientXMPP):

    # an abstract identifier for opsec purposes

    identifier = 'unknown'
    sessionid = 'unknown'

    def __init__(self, identifier, jid, password, clients):
        super(Jabber, self).__init__(jid, password)
        self.identifier = identifier
        self.clients = clients
        # ping
        self.register_plugin('xep_0199')
        # service discovery
        self.register_plugin('xep_0030')
        # capabilities
        self.register_plugin('xep_0115')

        ## add xmpp event handlers
        self.add_event_handler('ssl_invalid_cert', self.discard)
        self.add_event_handler('session_start', self.start)
        self.add_event_handler('failed_auth', self.failure)

    def failure(self, event):
        _logger.log('[' + str(self.identifier) + '] Unable to login user',_logger.LogLevel.ERROR)
        self.disconnect(reconnect=False, wait=False, send_close=True)

    def discard(self, event, *args):
        return

    def start(self, event):
        #self.send_presence(ptype='away', ppriority='-1')

        # this is the meat of this tool.
        # an unconfigured python client will have a default client type as "bot"
        # we do not want this.

        # https://xmpp.org/extensions/xep-0030.html#schemas-info
        clients = self.clients
        for client in clients:

            jid_short, detail= client.split('/')

            # ping w/ xep 0199
#            ping = jid_ping(self, client)
#            print('ping for {0}: {1}'.format(jid_short, ping))

            # service discovery

            try:
                result = self['xep_0030'].get_info(
                    jid = client,
                    local = False,
                    block = True,
                )
            except sleekxmpp.exceptions.IqTimeout as error:
                # maybe setup a retry loop? idk
                _logger.log('[' + __name__ + '] Disconnecting due to timeout on get_info query to {0}'.format(self.sessionid),_logger.LogLevel.WARNING)
                print('ERRRROR')
                print(jid_short)
                continue
            except sleekxmpp.exceptions.IqError as error_xml:
                error = xmltodict.parse(str(error_xml))
                _logger.log('[' + __name__ + '] Client {0} does not support disco_info queries'.format(self.sessionid),_logger.LogLevel.WARNING)
                print('ERRRROR')
                print(jid_short)
                continue

            # process disco_info

            disco_info = xmltodict.parse(str(result))

#            print(disco_info)

            iq = disco_info.get('iq')
            if iq == None:
                print(disco_info)
            query = iq.get('query')


            # https://itunes.apple.com/us/app/im-instant-messenger/id285688934?mt=8
            # seems not to give a useful response to disc_info queries, eg:
            # OrderedDict([('@xmlns', 'http://jabber.org/protocol/disco#info'), ('feature', [OrderedDict([('@var', 'http://jabber.org/protocol/disco#info')]), OrderedDict([('@var', 'http://jabber.org/protocol/si/profile/file-transfer')])])])

            if query == None:
                print(disco_info)
                continue

            identity = query.get('identity')

            if identity == None:
                if detail == 'IM+' or detail == 'IM+ Android':
                    _logger.log('[' + __name__ + '] {0} using known shit client: IM+'.format(jid_short),_logger.LogLevel.WARNING)
                else:
                    print('mystery: {0} : {1}'.format(jid_short, query))

            c_features = query.get('feature')

            # nothing else useful in the identity query
            print(identity)
            if not identity == None:
                c_category = identity.get('@category')
                c_type = identity.get('@type')
                c_name = identity.get('@name')
            else:
                continue

            if len(c_features) < 1:
                print(jid_short, len(c_features), c_category, c_type, c_name)

            if c_type == 'bot':
                # default bot configuration for my spy tool
                print('EEEEEEEEEEEEEEEEEEE')

            if c_name == None:
                # default bot configuration for my spy tool
                print('EEEEEEEEEEEEEEEEEEE')
        self.disconnect(reconnect=False, wait=False, send_close=True)

def audit_bothunt():

    import common.credentials.broadcast as _jabber
    import common.logger as _logger
    import common.credentials.bothunt as _bothunt
    import common.ldaphelpers as _ldaphelpers
    import re
    import logging
    import requests
    import json

    import subprocess

    _logger.log('[' + __name__ + '] auditing jabber active sessions',_logger.LogLevel.INFO)

    j_user = _jabber.broadcast_user
    j_pass = _jabber.broadcast_password

    # fetch the session information from jabber
    # this runs fine even when ran as root

    data = subprocess.run(["sudo", "ejabberdctl", "connected_users_info"], stdout=subprocess.PIPE)

    # parse output
    stdout = data.stdout.decode('utf-8')
    clients = dict()

    regex = r"^" + j_user

    for raw_line in stdout.split('\n'):

        if raw_line == '': continue

        info = dict()
        jid, info['conn_type'], info['client_ip'], info['client_port'], info['client_priority'], info['node'], info['uptime'] = raw_line.split('\t')

        # don't match self
        if re.match(regex, jid):
            continue
        else:
            clients[jid] = info

    _logger.log('[' + __name__ + '] {0} active jabber sessions'.format(len(clients)),_logger.LogLevel.INFO)

    connected_clients = clients.keys()
    for client in connected_clients:
        cn, server = client.split('@')
        dn = 'ou=People,dc=triumvirate,dc=rocks'
        filterstr = 'cn={}'.format(cn)
        attributes = ['authGroup', 'characterName']
        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attributes)

        if code == False:
            msg = 'unable to connect to ldap'
            _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
            continue
        (dn, info), = result.items()

        charname = info['characterName']
        groups = info['authGroup']

        if not 'trisupers' in groups:
            clients.pop(client, None)

#    return
#    thing = 'rainbowarielmoon@triumvirate.rocks/6447582518372469981144650259794242310811493004068295965831'
#    thing = 'saekatyr@triumvirate.rocks/729827350702828396058635616511165752724531413542125212543'
#    clients = {thing: None}
    jabber = Jabber('bothunt', j_user, j_pass, clients)
    jabber.connect()
    jabber.process(block=False)

    return

