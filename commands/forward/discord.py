#!/usr/bin/python3

import time
import discord
import asyncio
import random
import re as _re

import common.credentials.discord as _discord
import common.logger as _logger

def start_discord(username, password, covername, handler, discord_queue):

    prefix = '[' + __name__ + '][' + username + '] '
    wait = random.randint(1,60)
    _logger.log(prefix + 'starting up. {0} ({1}) waiting {2} seconds'.format(covername, username, wait), _logger.LogLevel.INFO)
    time.sleep(wait)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client(loop=loop,cache_auth=False)

    @client.event
    async def on_ready():
        _logger.log(prefix + 'discord user {0} ({1}) connected'.format(covername, username), _logger.LogLevel.INFO)
        loginmsg = '```diff' + '\n' + '+ {0} online```'.format(covername)
        client.change_presence(game=None, status='invisible', afk=False)
        discord_queue.put(loginmsg)

    @client.event
    async def on_server_remove():
        _logger.log(prefix + 'discord user {0} ({1}) disconnected'.format(covername, username), _logger.LogLevel.INFO)
        loginmsg = '```diff' + '\n' + '+ {0} offline [remove]```'.format(covername)
        discord_queue.put(loginmsg)
    @client.event
    async def on_server_unavailable():
        _logger.log(prefix + 'discord user {0} ({1}) unavailable'.format(covername, username), _logger.LogLevel.INFO)
        loginmsg = '```diff' + '\n' + '+ {0} offline [unavailable]```'.format(covername)
        discord_queue.put(loginmsg)

    @client.event
    async def on_message(message):

        if message.mention_everyone:
            _logger.log(prefix + 'discord ping to user {0} ({1})'.format(covername, username), _logger.LogLevel.INFO)
            discord_queue.put(parse_message(str(covername), message))

    try:
        client.run(username, password)
    except Exception as error:
        _logger.log(prefix + 'Discord connection error on user {0} ({1}): {2}'.format(covername, username, error), _logger.LogLevel.ERROR)
        loginmsg = '```diff' + '\n' + '- {0} offline```'.format(covername)
        discord_queue.put(loginmsg)

def parse_message(cover, message):
    if cover == "horde":
        body = horde_parser(message)
    elif cover == "GOTG":
        body = gotg_parser(message)
    else:
        body = default_parser(message)

    return "**[{0}]** | __{1}__\n```css\n{2}```"\
        .format(cover, time.strftime("%H:%M:%S %z / %d-%m-%Y", time.localtime(None)), body)

def default_parser(message):
    return "FROM: {0} | {1}\nCHANNEL: {2}\n--------------------\n{3}"\
        .format(str(message.author),str(message.server), str(message.channel), str(message.content).replace('@','#'))

def gotg_parser(message):
    try:
        text = message.content.splitlines()

        ping_from = text[1].split(" ", 1)[-1]
        ping_to = text[2].split(" ", 1)[-1]

        return "FROM: {0} | {1}\nTO: {2} (CHANNEL:{3})\n--------------------\n{4}" \
            .format(ping_from, str(message.server), ping_to, str(message.channel),
                    str("\n".join(text[3:])).replace('@', '#'))
    except Exception:
        return default_parser(message)

def horde_parser(message):
    try:
        text = message.content

        author_clean = message.author

        mentions = [mention for mention in text.split() if mention.startswith('@')]

        textwords = [word for word in text if word not in mentions]

        return "FROM:  | {1}\nTO: {2} (CHANNEL:{3})\n--------------------\n{4}" \
            .format(author_clean, str(message.server), ", ".join(mentions).replace('@', ''), str(message.channel),
                    str(text).replace('@', '#'))
    except Exception:
        return default_parser(message)
