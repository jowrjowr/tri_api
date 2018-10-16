# broadcast a message to a given jabber group

import sleekxmpp
import time
import common.logger as _logger
import sleekxmpp.plugins.xep_0033 as xep_0033
import MySQLdb as mysql

from sleekxmpp import ClientXMPP, Message
from sleekxmpp.exceptions import IqError, IqTimeout
from sleekxmpp.xmlstream import register_stanza_plugin
from common.discord_api import discord_forward

class BroadcastBot(ClientXMPP):

    def __init__(self, jid, password, recipients, msg):

        ClientXMPP.__init__(self, jid, password)

        self.recipients = recipients
        self.msg = msg

        # xmpp configuration
        self.ca_certs = None
        self.whitespace_keepalive = False
        self.auto_reconnect = True
        self.response_timeout = 5

        self.register_plugin('xep_0033') # multicast
        self.register_plugin('xep_0030') # service discovery
        # add handlers
        self.add_event_handler('failed_auth', self.failure)
        self.add_event_handler('session_start', self.start)
        self.add_event_handler('ssl_invalid_cert', self.discard)

        # configure pingbomb


    def discard(self, event):
        # https://github.com/fritzy/SleekXMPP/issues/423
        # it is NOT liking the ssl cert...
        return

    def failure(self, event):
        _logger.log('[' + __name__ + '] Unable to login user {0}'.format(self.boundjid),_logger.LogLevel.ERROR)

    def start(self, event):
        _logger.log('[' + __name__ + '] broadcast user online: {0}'.format(self.boundjid),_logger.LogLevel.DEBUG)

        # construct the multi-user msg
        # see: https://github.com/fritzy/SleekXMPP/wiki/Stanzas:-Message
        message = self.Message()
        message['to'] = 'multicast.triumvirate.rocks'
        message['from'] = 'sovereign@triumvirate.rocks'
        message['body'] = self.msg
        message['type'] = 'noreply'
        message['replyto'] = message['from']

        # add the multiple targets. works fine with just one, as well.
        # see: https://xmpp.org/extensions/xep-0033.html
        for jid in self.recipients:
            message['addresses'].addAddress(jid=jid, atype='bcc')

        try:
            result = message.send()
            for address in message['addresses']:
                print(address.get_delivered())
            _logger.log('[' + __name__ + '] User {0} sent broadcast'.format(self.boundjid),_logger.LogLevel.DEBUG)
        except sleekxmpp.exceptions.IqError as error:
            _logger.log('[' + __name__ + '] User {0} unable to send message: {1}'.format(self.boundjid, error),_logger.LogLevel.ERROR)
        finally:
            self.disconnect(wait=True)
            pass

def start_jabber(users, message):

    import common.credentials.broadcast as _broadcast

    user = _broadcast.broadcast_user + '/broadcast'
    password = _broadcast.broadcast_password

    try:
        jabber = BroadcastBot(user, password, users, message)
        jabber.connect(address=('triumvirate.rocks',5222))
        jabber.process(block=False)
        return True
    except Exception as error:
        _logger.log('[' + __name__ + '] User {0} unable to broadcast to users {0}: {1}'.format(user, error),_logger.LogLevel.ERROR)
        return False

def broadcast(message, group=None, corpid=None):

    # broadcast a message to all the members of a given ldap group

    import math
    import common.logger as _logger
    import common.credentials.database as _database
    import common.ldaphelpers as _ldaphelpers
    from tri_core.common.sashslack import sashslack
    from concurrent.futures import ThreadPoolExecutor
    from collections import defaultdict
    from queue import Queue

    dn = 'ou=People,dc=triumvirate,dc=rocks'
    attrlist=[ 'cn', 'uid', 'altOf', 'lastLogin' ]

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return None
    cursor = sql_conn.cursor()


    # skip certain users
    skip = [ 'sovereign' ]

    if corpid is not None:
        # broadcast message to entire authgroup

        _logger.log('[' + __name__ + '] broadcasting to corporation: {}'.format(corpid),_logger.LogLevel.INFO)
        _logger.log('[' + __name__ + '] broadcast message: {}'.format(message),_logger.LogLevel.INFO)

        # send message to sash slack

        if corpid == 98203328:
            # send to #_ops for now
            sashslack(message, 'structures')

        filterstr='(&(objectclass=pilot)(corporation={0})(esiRefreshToken=*)(teamspeakuid=*))'.format(corpid)

        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

        if code == False:
            msg = 'unable to fetch ldap information: {}'.format(error)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return None

        if result == None:
            msg = 'no users in group {0}'.format(charid)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
            return None

        _logger.log('[' + __name__ + '] total users in corp {0}: {1}'.format(corpid, len(result)),_logger.LogLevel.INFO)

    if group is not None:
        # broadcast message to an authgroup


        # send message to discord

        discord_msg = '@everyone\n' + message

        if group == 'triumvirate':
            discord_forward(discord_msg, server=358117641724100609, dest='general')
        elif group == 'trisupers':
            discord_forward(discord_msg, server=358117641724100609, dest='supers')
        elif group == 'administration':
            discord_forward(discord_msg, server=358117641724100609, dest='administration')
        elif group == 'skyteam':
            discord_forward(discord_msg, server=358117641724100609, dest='skyteam')
        elif group == 'skirmishfc':
            discord_forward(discord_msg, server=358117641724100609, dest='skirmish')

        # send message to sash slack
        sashslack(message, group)

        # send to jabber

        filterstr='(&(objectclass=pilot)(authGroup={0})(esiRefreshToken=*)(teamspeakuid=*))'.format(group)
        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

        if code == False:
            msg = 'unable to fetch ldap information: {}'.format(error)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return None

        if result == None:
            msg = 'no users in group {0}'.format(charid)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
            return None

        _logger.log('[' + __name__ + '] total users in authgroup {0}: {1}'.format(group, len(result)),_logger.LogLevel.INFO)

    users = list()

    for dn in result:
        cn = result[dn]['cn']
        charid = result[dn]['uid']
        altof = result[dn]['altOf']
        lastlogin = result[dn]['lastLogin']
        jid = cn + '@triumvirate.rocks'

        if lastlogin is None:
            lastlogin = 0

        if time.time() - lastlogin > 15*86400:
            # don't ping people who aren't logging in
            continue

        if altof is not None:
            # don't ping alts
            continue

        if cn not in skip:
            users.append(jid)

    _logger.log('[' + __name__ + '] pinging {0} users'.format(len(users)),_logger.LogLevel.INFO)

    # break up into chunks to make [undocumented] ejabberd limitations happy

    data = []
    chunksize = 250
    for user in users:
        data.append(user)
    length = len(data)
    chunks = math.ceil(length / chunksize)
    for i in range(0, chunks):
        chunk = data[:chunksize]
        del data[:chunksize]
        _logger.log('[' + __name__ + '] sending broadcast to {0} user block'.format(len(chunk)),_logger.LogLevel.INFO)
        start_jabber(chunk, message)
