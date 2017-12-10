#!/usr/bin/python3

import sleekxmpp
import xmltodict
import time
import common.logger as _logger
import common.database as _database
import MySQLdb as mysql
import discord
import argparse

from queue import Queue
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
from common.discord_api import discord_forward
import common.credentials.discord as _discord
from concurrent.futures import ThreadPoolExecutor

from commands.forward.discord import start_discord
from commands.forward.jabber import start_jabber
from commands.forward.telegram import start_telegram
from commands.forward.slack import start_slack

def forward():

    # allow differentiation for spy targets?

    _logger.log('[' + __name__ + '] spy forwarder starting up', _logger.LogLevel.DEBUG)

    # get our list of spies
    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        sys.exit(1)

    cursor = sql_conn.cursor()
    query = 'SELECT id, covername, username, password, server, handler, server_type FROM Spies'
    try:
        count = cursor.execute(query)
        rows = cursor.fetchall()
    except Exception as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        sys.exit(1)
    finally:
        cursor.close()
        sql_conn.close()

    _logger.log('[' + __name__ + '] registered spies: {0}'.format(count), _logger.LogLevel.INFO)

    # shoot each discord instance into a thread that will operate
    # asynchronously, while sending messages into a queue that also operates
    # in an async fashion.

    pool = ThreadPoolExecutor(count + 5)
    discord_queue = Queue()

    # telegram
    # this exists outside kinda with how the auth works and limited uses
    #pool.submit(start_telegram, discord_queue)

    for row in rows:
        covername = row[1]
        username = row[2]
        password = row[3]
        server = row[4]
        handler = row[5]
        server_type = row[6]

        if server_type == 'discord':
            pool.submit(start_discord, username, password, covername, handler, discord_queue)
        elif server_type == 'slack':
            pass
            #pool.submit(start_slack, username, password, covername, handler, server, discord_queue)
        elif server_type == 'jabber':
            jid = username + '@' + server
            pool.submit(start_jabber, jid, password, covername, handler, discord_queue)

    while True:
        _logger.log('[' + __name__ + '] waiting for queue messages', _logger.LogLevel.INFO)
        item = discord_queue.get()
        _logger.log('[' + __name__ + '] new discord queue item'.format(item), _logger.LogLevel.INFO)
        pool.submit(discord_forward, item)
        discord_queue.task_done()
        time.sleep(1)

class parseaction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(parseaction, self).__init__(option_strings, dest, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

        # setup logging
        if namespace.logname == None:
            filename = "spy"
        else:
            filename = namespace.logname

        _logger.LogSetup(namespace.loglevel, filename, namespace.logdir)

        # actually do things

        forward()

def add_arguments(parser):
    parser.add_argument("--spy",
        nargs=0,
        action=parseaction,
        choices = [ 'all' ],
        help='spying on people!',
    )
