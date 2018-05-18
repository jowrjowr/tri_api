import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.credentials.discord as _discord
import common.request_esi
import redis
import logging
import discord
import asyncio
import time

# new logging mappings
from common.logger import getlogger_new as getlogger

def discord_allmembers(token=None, target_server=None, exclude=[], include=[]):

    # don't care about extraneous discord noise

    logging.getLogger('discord.state').setLevel(logging.CRITICAL)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client(loop=loop,cache_auth=False)

    users = dict()
    @client.event
    async def on_ready():
        msg = 'discord connected'
        logging.info(msg)
        await client.change_presence(game=None, status='invisible', afk=False)
        servers = client.servers
        for server in servers:

            # because of course server.id is a fucking string

            server_id = int(server.id)

            if server_id != target_server and target_server is not None:
                # if a discord server id is specified, don't bother looking at others.
                continue

            users[server_id] = []

            large = server.large
            if large == True:
                # as per discord api, "large" servers won't return offline members
                client.request_offline_members(server)

            if server.name in exclude:
                msg = 'excluding discord: {0}'.format(server.name)
                logging.debug(msg)
                # do not fetch members from this named discord
                continue

            if server.name in include or include == []:
                msg = 'including discord: {0}'.format(server.name)
                logging.debug(msg)
                # only fetch specifically included discords
                pass
            else:
                msg = 'excluding discord: {0}'.format(server.name)
                logging.debug(msg)
                continue

            members = server.members

            for member in members:
                member_detail = dict()

                # map the join time to epoch
                joined_at = member.joined_at
                joined_at = time.mktime(joined_at.timetuple())
                joined_at = int(joined_at)

                # roles

                roles = []
                for role in member.roles:
                    roles.append(role.name)

                member_detail['discorduid'] = int(member.id)
                member_detail['bot'] = member.bot
                member_detail['name'] = member.name
                member_detail['display_name'] = member.display_name
                member_detail['server_name'] = member.server.name
                member_detail['server_id'] = int(server.id)
                member_detail['discriminator'] = member.discriminator
                member_detail['joined_at'] = joined_at
                member_detail['status'] = str(member.status)
                member_detail['member_nick'] = member.nick
                member_detail['top_role'] = str(member.top_role)
                member_detail['roles'] = roles
                member_detail['server_permissions'] = member.server_permissions.value
                member_detail['object'] = member

                users[server_id].append(member_detail)

        await client.close()
    try:
        client.run(token)
        msg = 'discord disconnected'
        logging.debug(msg)
        return users
    except Exception as error:
        msg = 'discord connection error: {0}'.format(error)
        logging.critical(msg)
        return False

def authgroup_mapping(group):

    # mappings of authgroups to discord roles
    if group == 'public':           return '@everyone'
    if group == 'discordadmin':     return 'Director'
    if group == 'skyteam':          return 'Skyteam FC'
    if group == 'skirmishfc':       return 'Skirmish FC'
    if group == '500percent':       return '500percent'

    # no sale
    return None

def discord_changenick(token=None, target_server=None, member=None, nickname=None):

    # chage nickname of a member

    logging.getLogger('discord.state').setLevel(logging.CRITICAL)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client(loop=loop,cache_auth=False)

    users = dict()
    @client.event
    async def on_ready():
        msg = 'discord connected'
        logging.debug(msg)
        try:
            await client.change_nickname(member, nickname)
        except Exception as e:
            msg = 'unable to change nick of {0}: {1}'.format(member.name, e)
            logging.error(msg)
        await client.close()

    try:
        client.run(token)
        msg = 'discord disconnected'
        logging.debug(msg)
    except Exception as error:
        msg = 'discord connection error: {0}'.format(error)
        logging.critical(msg)
        return False


def discord_message_user(token=None, member=None, message=None):

    # send a message to a user

    logging.getLogger('discord.state').setLevel(logging.CRITICAL)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client(loop=loop,cache_auth=False)

    users = dict()
    @client.event
    async def on_ready():
        msg = 'discord connected'
        logging.debug(msg)

        try:
            await client.send_message(member, content=message)
        except Exception as error:
            msg = 'unable to send message to member {0}: {1}'.format(member.name, error)
            logging.error(msg)
        await client.close()

    try:
        client.run(token)
        msg = 'discord disconnected'
        logging.debug(msg)
    except Exception as error:
        msg = 'discord connection error: {0}'.format(error)
        logging.critical(msg)
        return False

def discord_kick_user(token=None, member=None, message=None):

    # kick user

    logging.getLogger('discord.state').setLevel(logging.CRITICAL)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client(loop=loop,cache_auth=False)

    users = dict()
    @client.event
    async def on_ready():
        msg = 'discord connected'
        logging.debug(msg)

        try:
            await client.kick(member)
        except Exception as error:
            msg = 'unable to kick member {0}: {1}'.format(member.name, error)
            logging.error(msg)
        await client.close()

    try:
        client.run(token)
        msg = 'discord disconnected'
        logging.debug(msg)
    except Exception as error:
        msg = 'discord connection error: {0}'.format(error)
        logging.critical(msg)
        return False

def discord_changeroles(token=None, target_server=None, member=None, roles_add=[], roles_del=[]):

    # adjust roles on a user

    logging.getLogger('discord.state').setLevel(logging.CRITICAL)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = discord.Client(loop=loop,cache_auth=False)

    users = dict()
    @client.event
    async def on_ready():
        msg = 'discord connected'
        logging.debug(msg)

        # fetch the relevant server object

        server = None
        for item in client.servers:
            if int(item.id) == target_server:
                server = item

        role_object_add = []
        role_object_del = []

        # map the role names to role objects

        for role in server.roles:
            if role.name in roles_add:
                role_object_add.append(role)
            if role.name in roles_del:
                role_object_del.append(role)

        # apply the changes

        if len(role_object_add) > 0:
            try:
                await client.add_roles(member, *role_object_add)
            except Exception as e:
                msg = 'unable to modify roles on {0}: {1}'.format(member.name, e)
                logging.error(msg)
        if len(role_object_del) > 0:
            try:
                await client.remove_roles(member, *role_object_del)
            except Exception as e:
                msg = 'unable to modify roles on {0}: {1}'.format(member.name, e)
                logging.error(msg)

        await client.close()

    try:
        client.run(token)
        msg = 'discord disconnected'
        logging.debug(msg)
    except Exception as error:
        msg = 'discord connection error: {0}'.format(error)
        logging.critical(msg)
        return False

def audit_discord_perms():

    logger = getlogger('discord.audit')
    msg = 'discord auditing'
    logger.info(msg)

    bot_token = 'MzQ1MzkzMjA0Nzg0MjY3MjY1.DJ9p_Q.e2qHsXSgAy_Tb-ATApTFFsvMVmQ'
    bot_discorduid = 345393204784267265
    server = 358117641724100609
    logging.getLogger('discord.audit').setLevel(logging.DEBUG)

    # these discord roles are manually assigned or everyone gets

    ignore_roles = ['Admin', 'TRI Friends', '@everyone', 'production', 'rorqcoordination']

    # these roles are ones the bot can't manage

    above_bot = [ 'Admin' ]

    # redis
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        msg = 'Redis connection error: ' + str(err)
        logger.error(msg)
    except Exception as err:
        msg = 'Redis generic error: ' + str(err)
        logger.error(msg)

    # fetch all the members from the social discord

    users = discord_allmembers(token=bot_token, target_server=server)

    # trim to one item

    userdata = users[server]

    # iterate through and populate with core ldap data if possible

    for user in userdata:

        # don't try to audit self

        if user['discorduid'] == bot_discorduid:
            continue

        dn = 'ou=People,dc=triumvirate,dc=rocks'
        filterstr = '(discorduid={0})'.format(user['discorduid'])
        attrlist = ['authGroup', 'characterName', 'corporation', 'corporationName',
            'discorduid', 'discordRefreshToken', 'discord2fa', 'esiRefreshToken', 'uid', 'alliance']
        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

        if result is None:

            # unregisterds lose roles immediately, then are kicked "later"

            msg = 'discord user {0} ({1}) unregistered in core'.format(user['name'], user['display_name'])
            message = 'You are unregistered on TRI CORE, but you have meaningful roles.\n'
            message += 'These roles are being removed until you REGISTER on https://www.triumvirate.rocks/comms\n'
            # purge the user's roles

            purge_roles = set(user['roles']) - set(ignore_roles)
            purge_roles = list(purge_roles)

            if len(purge_roles) > 0:

                # no point in making noises for users that won't be affected
                logger.info(msg)

                # warn the user
                discord_message_user(token=bot_token, member=user['object'], message=message)
                # purge the roles
                discord_changeroles(token=bot_token, target_server=server, member=user['object'], roles_add=list(missing_roles), roles_del=purge_roles)
                pass

            # purge if they have no roles whatsoever:
            # don't want to purge people with manual roles (tri friends)

            roles = set(user['roles']) - set(['@everyone'])

            if not roles:
                # start the clock that the character has been seen
                # a cache time of 10 days lets this get purged from redis well after i'm done with it

                timestamp = r.get('discordaudit:unregistered:{0}'.format(user['discorduid']))

                if timestamp is None:
                    r.setex('discordaudit:unregistered:{0}'.format(user['discorduid']), 864000, time.time())
                    message = 'Unregistered and role-free idlers are not allowed on the TRI discord.\n'
                    message += 'You have 24 hours before being purged.\n'
                    discord_message_user(token=bot_token, member=user['object'], message=message)

                difference = time.time() - float(timestamp)

                if difference >= 86400:
                    message = "You've been kicked from the TRI discord. Feel free to re-register on CORE\n"
                    message += "...or get an invite + roles from leadership"
                    discord_message_user(token=bot_token, member=user['object'], message=message)

                    msg = "kicking unregistered user {0}".format(user['name'])
                    logger.info(msg)

                    discord_kick_user(token=bot_token, member=user['object'])

            continue
        else:
            (dn, info), = result.items()

        corpid = info['corporation']

        # see if this user can be managed by the bot

        managable = True

        if set(user['roles']).intersection(set(above_bot)):
            # check a nonzero intersection of the user roles and any "Above the bot" roles
            managable = False

        # fetch corp ticker

        request_url = 'corporations/{0}/'.format(corpid)
        code, result = common.request_esi.esi(__name__, request_url, 'get', version='v4')

        if code != 200:
            # something broke severely
            msg - 'corporations API error {0}: {1}'.format(code, result['error'])
            logger.error(msg)

            # can't process without the ticker.
            continue
        else:
            ticker = result.get('ticker')


        # construct appropriate user name

        if ticker is None:
            correct_name = '{0}'.format(info['characterName'])
        else:
            correct_name = '[{0}] {1}'.format(ticker, info['characterName'])

        if user['display_name'] != correct_name and managable:
            msg = 'wrong name. using: {0}, should have: {1}'.format(user['display_name'], correct_name)
            discord_changenick(token=bot_token, target_server=server, member=user['object'], nickname=correct_name)

        # if the discord or ESI tokens have been removed, remove their roles.

        if info['discordRefreshToken'] is None:

            message = "Your discord token is no longer valid.\n"
            message += "Roles are being removed until you re-register discord on TRI CORE\n"

            purge_roles = set(user['roles']) - set(ignore_roles)
            purge_roles = list(purge_roles)

            # only take action on actual roles to remove

            if purge_roles:
                msg = "character {0} no longer has a discord refresh token - removing roles".format(info['characterName'])
                logger.info(msg)

                discord_message_user(token=bot_token, member=user['object'], message=message)
                discord_changeroles(token=bot_token, target_server=server, member=user['object'], roles_del=purge_roles)
            continue

        if info['esiRefreshToken'] is None:

            message = "Your ESI token is no longer valid.\n"
            message += "Roles are being removed until you reconnect to TRI CORE\n"

            purge_roles = set(user['roles']) - set(ignore_roles)
            purge_roles = list(purge_roles)

            # only take action on actual roles to remove

            if purge_roles:
                msg = "character {0} no longer has a ESI refresh token - removing roles".format(info['characterName'])
                logger.info(msg)

                discord_message_user(token=bot_token, member=user['object'], message=message)
                discord_changeroles(token=bot_token, target_server=server, member=user['object'], roles_del=purge_roles)

            continue


        # construct the correct discord roles for this user
        # this will be absolutely correct as far as ldap is concerned

        correct_roles = []

        # should maybe add something for banned users maybe, but they
        # will get purged of all meaningful roles anyway

        # map ldap authgroups to discord roles
        for authgroup in info['authGroup']:
            mapping = authgroup_mapping(authgroup)
            if mapping is not None:
                correct_roles.append(mapping)

        if info['alliance'] == 933731581:

            # tri role and corp tags only meaningful if in tri
            correct_roles.append('[TRI]')
            correct_roles.append('[{0}]'.format(ticker))

        missing_roles = set(correct_roles) - set(user['roles'])
        extra_roles = set(user['roles']) - set(correct_roles)
        extra_roles = extra_roles - set(ignore_roles)

        if extra_roles:
            msg = 'user {0} has extra roles: {1}'.format(user['name'], extra_roles)
            logger.info(msg)

        if missing_roles:
            msg = 'user {0} has missing roles: {1}'.format(user['name'], missing_roles)
            logger.info(msg)

        if extra_roles or missing_roles:
            if managable:
                discord_changeroles(token=bot_token, target_server=server, member=user['object'], roles_add=list(missing_roles), roles_del=list(extra_roles))
