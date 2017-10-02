#!/usr/bin/python3

import sleekxmpp
import xmltodict
import asyncio
import time
import common.logger as _logger
from queue import Queue
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout

class JabberForwarder(ClientXMPP):

    def __init__(self, jid, password, covername, handler, queue):
        # connect to jabber

        jid = jid + '/IM+'

        ClientXMPP.__init__(self, jid, password)

        self.queue = queue
        self.covername = covername
        self.handler = handler
        self.status = 'away'
        self.priority = '100' # -127 to 127 range, higher = more priority over multiple clients
        self.logprefix = '[' + __name__ + '][' + jid + '] '

        # xmpp configuration
        self.whitespace_keepalive = True
        self.whitespace_keepalive_interval = 30
        self.auto_reconnect = True
        self.register_plugin('xep_0199') # Ping
        self.register_plugin('xep_0186') # invisibility
        self.register_plugin('xep_0030') # service discovery
        ## add xmpp event handlers

        # https://github.com/fritzy/SleekXMPP/wiki/Event-Index
        self.add_event_handler('ssl_invalid_cert', self.discard)
        self.add_event_handler('session_start', self.start)
        self.add_event_handler('message', self.message)
        self.add_event_handler('failed_auth', self.failure)
        self.add_event_handler('presence', self.presence)

        self['xep_0030'].set_node_handler(
            'get_info',
            jid=None, node=None,  # this will make the handler respond globally, for any JID+node
            handler=self.disco_info
        )
    def discard(self, event, *args):
        return

    def header(self):
        now = time.localtime(None)
        now_friendly = time.strftime("%Y-%m-%d @ %H:%M:%S %z", now)
        prefix = '[' + str(self.covername) + ']'
        prefix = prefix + '\t' + 'Time: {0}, covername: {1}'.format(str(now_friendly), self.covername)
        prefix = prefix + '\n'
        prefix = prefix + '----------' + '\n'
        return prefix

    def disco_info(self, jid, node, iq):
        # configure bot identity
        # https://github.com/fritzy/SleekXMPP/wiki/XEP-0030:-Working-with-Service-Discovery
        # don't _really_ care, but logging if someone is being nosy to me cant hurt
        disco_details = xmltodict.parse(str(iq))
        noseyprick = disco_details['iq']['@from']
        _logger.log(self.logprefix + 'Discovery info query from {0}'.format(noseyprick),_logger.LogLevel.WARNING)
        info = self['xep_0030'].stanza.DiscoInfo()
        info.add_identity(
            category  = 'client',
            itype     = 'pc',
            name      = 'Pidgin',
        )
        return info

    def failure(self, event):
        _logger.log(self.logprefix + 'Unable to login user',_logger.LogLevel.ERROR)
        loginmsg = '```diff' + '\n' + '- {0} offline```'.format(self.covername)
        self.queue.put(loginmsg)
    def offline(self, event):
        _logger.log(self.logprefix + 'User offline. Reconnecting',_logger.LogLevel.WARNING)
        loginmsg = '```diff' + '\n' + '- {0} offline```'.format(self.covername)
        self.queue.put(loginmsg)
        self.disconnect(reconnect=True, wait=False, send_close=False)
    def nothing(self, event):
        pass
    def presence(self, event):

        # the only presence we really care about is our own.
        # it's worth knowing spy self-activity

        xml = xmltodict.parse(str(event))
        presence_from = xml['presence']['@from'].split('/')
        whoiam = str(self.boundjid).split('/')

        if presence_from[0] == whoiam[0]:

            try:
                if xml['presence']['status'] == 'Online':
                    loginmsg = '```diff' + '\n' + '- {0} duplicate login```'.format(self.covername)
                    self.queue.put(loginmsg)
                    _logger.log(self.logprefix + 'Duplicate login',_logger.LogLevel.WARNING)
            except KeyError:
                # for some reason not every presence has status?
                pass

    def start(self, event):
        # the bot sits and does nothing once logged in. nothing happens until
        # a message event is received.
        # try to set myself as invisible or at least "not online"
        try:
            self.plugin['xep_0186'].set_invisible()
            _logger.log(self.logprefix + 'User invisible via xep_0186',_logger.LogLevel.INFO)

        except sleekxmpp.exceptions.IqError as error:
            # xep 0186 is not available always. not being there is no big deal.
            # so we'll have to settle for away

            # 'unavailable' works too well with python - you get nothing from the server.
            # the spark client does not do this for some reason?
            pass
        finally:
            self.send_presence(ptype=self.status, ppriority=self.priority)
            loginmsg = '```diff' + '\n' + '+ {0} online```'.format(self.covername)
            self.queue.put(loginmsg)
            _logger.log(self.logprefix + 'User online',_logger.LogLevel.INFO)


    def message(self, event):

        # forward the message to discord, including who sent the message

        xml = xmltodict.parse(str(event))
        presence_from = xml['message']['@from'].split('/')
        _logger.log(
            self.logprefix + 'forwarding message to discord: ',
            _logger.LogLevel.INFO
        )
        _logger.log(
            self.logprefix + ': {0}: {1}'.format(presence_from[0],event['body']),
            _logger.LogLevel.INFO
        )
        self.queue.put(parse_message(self.covername, presence_from[0],event['body']))

def start_jabber(jid, password, covername, handler, discord_queue):
    _logger.log('[' + __name__ + '] starting spy {0}'.format(jid), _logger.LogLevel.INFO)

    jabber = JabberForwarder(jid, password, covername, handler, discord_queue)

    # this is a polipo http proxy. could possibly use xep_0065 for a socks5 proxy.
    jabber.proxy_config['host'] = '127.0.0.1'
    jabber.proxy_config['port'] = 8123
    jabber.proxy_config['username'] = ''
    jabber.use_proxy = True

    jabber.connect()
    # explicitly nonblocking - care for your threads!
    jabber.process(block=False)

def parse_message(cover, presence_from, message):
    if cover == "fcon":
        body = fcon_parser(presence_from, message)
    elif cover == "brave":
        body = brave_parser(presence_from, message)
    elif cover == "test":
        body = test_parser(presence_from, message)
    else:
        body = message

    if cover == "fcon" or cover == "test":
        return "@here\n**[{0}]** | __{1}__\n```css\n{2}```" \
            .format(cover, time.strftime("%H:%M:%S %z / %d-%m-%Y", time.localtime(None)), body)
    else:
        return "**[{0}]** | __{1}__\n```css\n{2}```"\
            .format(cover, time.strftime("%H:%M:%S %z / %d-%m-%Y", time.localtime(None)), body)

def fcon_parser(presence_from, message):
    try:
        text = "\n".join(message.splitlines()[3:-1]).replace(' || ', '\n')

        footer = message.splitlines()[-1].split(' to ')

        target = footer[-2].split(' @ ')[0][1:-1]

        author = ' to '.join(footer[:-2]).split('broadcast from')[1].lstrip()

        return "FROM: {0} | {1}\nTO: {2}\n--------------------\n{3}" \
            .format(author, presence_from, target, str(text).replace('@', '#'))
    except Exception:
        return message

def brave_parser(presence_from, message):
    try:
        text = "\n".join(message.splitlines()[:-1])

        footer = message.splitlines()[-1].split('; ')

        target = footer[1].split(': ')[1]

        author = footer[0].split(': ')[1]

        return "FROM: {0} | {1}\nTO: {2}\n--------------------\n{3}" \
            .format(author, presence_from, target, str(text).replace('@', '#'))
    except Exception:
        return message

def test_parser(presence_from, message):
    try:
        text = "\n".join(message.splitlines()[1:-1])

        footer = message.splitlines()[-1].split(' to ')

        target = footer[-1].split(' @ ')[0]

        author = ' to '.join(footer[:-1]).split('SENT BY')[1].lstrip()

        return "FROM: {0} | {1}\nTO: {2}\n--------------------\n{3}" \
            .format(author, presence_from, target, str(text).replace('@', '#'))
    except Exception:
        return message

