import redis
import yaml
import random
import time
import datetime
import asyncio
import requests
import common.logger as _logger
import common.ldaphelpers as _ldaphelpers
import common.request_esi
import common.esihelpers as _esihelpers
from tri_core.common.testing import vg_alliances
from common.discord_api import discord_forward

def maint_notifications():

    # setup logging

    _logger.log('[' + __name__ + '] notification huffer online',_logger.LogLevel.INFO)

    task = asyncio.Task(run_notifications_forever())
    loop = asyncio.get_event_loop()
    loop.run_forever()

async def run_notifications_forever():

    while True:

        try:
            run_notifications()
        except Exception as e:
            print(e)
        finally:
            time.sleep(60)

def run_notifications():

    _logger.log('[' + __name__ + '] fetching notifications',_logger.LogLevel.INFO)

    # setup connections

    r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except redis.exceptions.ConnectionRefusedError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except Exception as err:
        logger.error('[' + __name__ + '] Redis generic error: ' + str(err))


    # fetch all the uids that have usable tokens for each alliance

    data = {}

    for alliance in vg_alliances():

        dn = 'ou=People,dc=triumvirate,dc=rocks'
        filterstr = '(&(esiScope=esi-characters.read_notifications.v1)'
        filterstr += '(|(corporationRole=Director)(corporationRole=Station_Manager))'
        filterstr += '(esiAccessToken=*)(alliance={0}))'.format(alliance)

        attrlist = ['uid', 'corporation', 'corporationName', 'alliance' ]

        code, result = _ldaphelpers.ldap_search(__name__, dn, filterstr, attrlist)

        data[alliance] = {}
        data[alliance]['corps'] = {}
        data[alliance]['notifications'] = {}

        if code == False:
            msg = 'unable to fetch ldap information: {}'.format(error)
            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.ERROR)
            return None

        for dn, info in result.items():

            corpid = int(info.get('corporation'))
            corpname = info.get('corporationName')
            uid = int(info.get('uid'))

            if data[alliance]['corps'].get(corpid) is None:
                # need to build the data structure
                data[alliance]['corps'][corpid] = {}
                data[alliance]['corps'][corpid]['corpname'] = corpname
                data[alliance]['corps'][corpid]['characters'] = []
                data[alliance]['corps'][corpid]['notifications'] = {}

            data[alliance]['corps'][corpid]['characters'].append(uid)

    # now fetch notifications for one char from each corp in each alliance


    msg = "total alliances: {0}".format(len(data))
    _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)

    for alliance in data.keys():

        msg = "total eligible corps in alliance {0}: {1}".format(alliance, len(data[alliance]['corps']))
        _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)

        tasks = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for corpid in data[alliance]['corps'].keys():

            corpname = data[alliance]['corps'][corpid]['corpname']
            characters = data[alliance]['corps'][corpid]['characters']
            char_amount = len(characters)
            msg = "total chars for corp {0}: {1}".format(corpname, char_amount)

            _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.DEBUG)
            # fetch a viable character ID

            charid = find_notification_char(r, characters)

            if charid is None:

                # need a character unaffected by cache time
                msg = "unable to find a character for corp {0}".format(corpname)
                _logger.log('[' + __name__ + '] {}'.format(msg),_logger.LogLevel.WARNING)
                continue

            tasks.append(asyncio.async(char_notifications(r, charid, corpname, corpid)))

        result = loop.run_until_complete(asyncio.gather(*tasks))

        for ally_nots, corpid, corp_nots in result:
            # merge in alliance notifications
            if ally_nots is not None:
                data[alliance]['notifications'].update(ally_nots)

            # merge in corp notifications
            if corp_nots is not None:
                data[alliance]['corps'][corpid]['notifications'].update(corp_nots)

        loop.close()

    # now that things are deduped and filtered, do the heavy processing

    for alliance in data.keys():

        # process each alliance-level notification

        ally_nots = len(data[alliance]['notifications'])

        msg = 'new notifications for alliance {0}: {1}'.format(alliance, ally_nots)
        _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.INFO)

        # sort it all

        latest_timestamp = 0

        notify_bulk = []
        bulk_msg = ''

        for not_id in sorted(data[alliance]['notifications']):

            notification = data[alliance]['notifications'][not_id]
            not_data = notification['raw_data']
            not_type = notification['type']
            not_timestamp = notification['timestamp_epoch']

            try:
                notification['data'] = notification_process(not_type, not_data)
            except Exception as e:
                print(e)
                continue

            if not_timestamp > latest_timestamp:
                # update redis to the current notification timestamp
                r.set('notification_checkpoint', not_timestamp)
                latest_timestamp = not_timestamp

            msg = format_for_discord(notification)

            bulk_msg_tmp = bulk_msg
            bulk_msg_tmp += '\n'
            bulk_msg_tmp += msg

            if len(bulk_msg_tmp) >= 2500:
                # this last message pushes it over the discord character limit
                notify_bulk.append(bulk_msg_tmp)
            else:
                bulk_msg = bulk_msg_tmp

        # iterate and dump alliance level into discord - don't ping the world

        for msg in notify_bulk:
            if len(msg) > 0:
                discord_forward(msg, dest='notification_spam')

        # send corp-level notifications
        for corpid in data[alliance]['corps'].keys():

            # process each corp-level notifications

            corpdata = data[alliance]['corps'][corpid]

            corp_nots = corpdata['notifications']
            corpname = corpdata['corpname']
            corp_not_count = len(corp_nots)
            corp_bulk_msg = ''

            if corp_not_count > 0:
                msg = 'new notifications for corporation {0}: {1}'.format(corpname, corp_not_count)
                _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.INFO)
            for not_id in sorted(corp_nots):

                notification = corp_nots[not_id]

                not_data = notification['raw_data']
                not_type = notification['type']
                not_timestamp = notification['timestamp_epoch']

                if not_timestamp > latest_timestamp:
                    # update redis to the current notification timestamp
                    r.set('notification_checkpoint', not_timestamp)
                    latest_timestamp = not_timestamp

                # process this pile of shit into something human legible
                corp_nots[not_id]['data'] = notification_process(not_type, not_data, charid=notification.get('charid'))

                msg = format_for_discord(notification)

                # discord bulk

                bulk_msg_tmp = bulk_msg
                bulk_msg_tmp += '\n'
                bulk_msg_tmp += msg

                # broadcast bulk

                corp_bulk_msg += '\n'
                corp_bulk_msg += msg

                if len(bulk_msg_tmp) >= 2500:
                    # this last message pushes it over the discord character limit
                    notify_bulk.append(bulk_msg_tmp)
                else:
                    bulk_msg = bulk_msg_tmp

            # ping specific corp

            if len(corp_bulk_msg) > 0:
                msg = "broadcasting to corp {0}".format(corpname)
                _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.INFO)

                request_url = 'https://api.triumvirate.rocks/core/corp/{0}/broadcast'.format(corpid)
                request = requests.post(request_url, data=corp_bulk_msg)

                if request.status_code is not 200:
                    msg = "unable to broadcast to corp {0}: {1}".format(corpname, request.text)
                    _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.ERROR)

        # add in the last one
        notify_bulk.append(bulk_msg)

        # iterate and dump into discord

        for msg in notify_bulk:
            if len(msg) > 0:
                discord_forward(msg, dest='notification_spam')

        if latest_timestamp == 0:
            latest_timestamp = int(time.time())

        r.set('notification_checkpoint', latest_timestamp)

@asyncio.coroutine
def char_notifications(r, charid, corpname, corpid):

    # fetch notifications from an appropriately selected character

    # what kinds of notifications do we care about?

    alliance_notifications = [
        'EntosisCaptureStarted', 'SovCommandNodeEventStarted', 'SovStructureDestroyed',
    ]

    corp_notifications = [
        'StructureUnderAttack', 'StructureLostShields', 'StructureLostArmor', 'TowerAlertMsg',
    ]

    # fetch the most recent notification epoch time from redis
    checkpoint = float(r.get('notification_checkpoint'))


    request_url = 'characters/{0}/notifications/'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

    if not code == 200:
        msg = 'characters/{0}/notifications error: {1}'.format(charid, result['error'])
        _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.WARNING)
        return None, None, None

    # process each notification from its raw-assed yaml

    corp_nots = {}
    ally_nots = {}

    for item in result:

        not_type = item.get('type')
        not_time = item.get('timestamp')
        not_id = item.get('notification_id')

        # convert the yaml to a dict
        try:
            not_data = yaml.load(item.get('text'))
        except Exception as e:
            # couldn't process the yaml. don't care.
            continue

        # process the timestamp

        # convert a date format like the following to epoch
        # 2017-12-24T08:14:00Z
        try:
            not_time_epoch = time.strptime(not_time, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as e:
            # don't especially care
            continue

        not_time_epoch = time.mktime(not_time_epoch)

        # use the redis checkpoint to determine what gets processed
        if not_time_epoch <= checkpoint:
            continue

        # okay, this is a new notification. process it.

        if not_type in alliance_notifications:
            # this is an alliance level notification.

            ally_nots[not_id] = {}
            ally_nots[not_id]['id'] = not_id
            ally_nots[not_id]['timestamp_epoch'] = not_time_epoch
            ally_nots[not_id]['timestamp'] = not_time
            ally_nots[not_id]['raw_data'] = not_data
            ally_nots[not_id]['type'] = not_type

        if not_type in corp_notifications:
            # this is a corp level notification.
            corp_nots[not_id] = {}
            corp_nots[not_id]['id'] = not_id
            corp_nots[not_id]['charid'] = charid
            corp_nots[not_id]['corpname'] = corpname
            corp_nots[not_id]['timestamp_epoch'] = not_time_epoch
            corp_nots[not_id]['timestamp'] = not_time
            corp_nots[not_id]['raw_data'] = not_data
            corp_nots[not_id]['type'] = not_type

    return ally_nots, corpid, corp_nots

def find_notification_char(r, characters):
    # locate a character out of redis that is capable of returning fresh corp/alliance
    # level notifications

    # grab a random character out of the pool, until one works.

    char_count = 0
    char_max = len(characters)
    cache_time = 10 * 60 # 10 minutes

    while char_count < char_max:
        charid = random.choice(characters)
        result = r.get('notification:{0}'.format(charid))

        if result is None:
            msg = "using character {0}".format(charid)
            _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.DEBUG)
            r.setex('notification:{0}'.format(charid), cache_time, True)
            return charid
        else:
            char_count += 1
    return None

def format_for_discord(data):
    # do all the bullshit to form these into formatted messages to jizz all over discord

    # common data

    timestamp = data['timestamp']
    not_type = data['type']

    structure_name = data['data'].get('structure_name')
    system_name = data['data']['solar_system_info']['solar_system_name']
    const_name = data['data']['solar_system_info']['constellation_name']
    region_name = data['data']['solar_system_info']['region_name']

    body = 'System: {0} (http://evemaps.dotlan.net/system/{0})\nConstellation: {1}\nRegion: {2}\n'.format(system_name, const_name, region_name)
    body += '\n--------------------\n\n'

    if not_type == 'StructureLostShields':
        structure_type = data['data']['structure_type_data']['name']
        body += "Corporation: {0}\n".format(data['corpname'])
        body += "{0} ({1}) is in armor reinforce.".format(structure_name, structure_type)

    if not_type == 'StructureLostArmor':
        structure_type = data['data']['structure_type_data']['name']
        body += "Corporation: {0}\n".format(data['corpname'])
        body += "{0} ({1}) is in hull reinforce.".format(structure_name, structure_type)

    if not_type == 'StructureUnderAttack':
        structure_type = data['data']['structure_type_data']['name']
        attacking_alliance = data['data']['attacker_affiliations']['alliancename']
        shield, armor, hull = data['data']['status']
        body += "Corporation: {0}\n".format(data['corpname'])
        body += "{0} ({1}) is being attacked.\n".format(structure_name, structure_type)
        body += "Shield %: {0} / Armor %: {1} / Hull %: {2}\n".format(shield, armor, hull)
        body += "Attacking alliance: {0}".format(attacking_alliance)

    if not_type == 'TowerAlertMsg':
        structure_type = data['data']['structure_type_data']['name']
        attacking_alliance = data['data']['attacker_affiliations']['alliancename']
        shield, armor, hull = data['data']['status']
        moon = data['data']['moon_info']['name']
        body += "{0} ({1}) is being attacked.\n".format(moon, structure_type)
        body += "Shield %: {0} / Armor %: {1} / Hull %: {2}\n".format(shield, armor, hull)
        body += "Attacking alliance: {0}".format(attacking_alliance)

    if not_type == 'StationServiceDisabled':

        # this one is kinda minimal. only one station in a system. doesn't say what service. etc.
        body += "Station Service Disabled"

    if not_type == 'SovStationEnteredFreeport':

        body += "Station is now freeport\n"

    if not_type == 'SovCommandNodeEventStarted':

        campaign_type = data['data']['campaign_type']
        body += "{0} campaign started".format(campaign_type)

    if not_type == 'EntosisCaptureStarted':
        structure_type = data['data']['structure_type_data']['name']

        body += "{0} is being captured".format(structure_type)

    if not_type == 'SovStructureDestroyed':
        structure_type = data['data']['structure_type_data']['name']
        body += "{0} kinda exploded".format(structure_type)

    msg = "**{0}** | __{1}__\n```css\n{2}```".format(not_type, timestamp, body)

    return msg

def notification_process(not_type, not_data, charid=None):

    # figure out what additional information needs to be requested from ESI or whatnot
    # in order to make these fucking notifications make sense
    # fuck me so much crap

    data = {}

    # pocos if we ever give a shit: OrbitalReinforced / OrbitalAttacked

    if not_type == 'StructureLostShields':
        # example:
        # {'solarsystemID': 30001154, 'structureID': 1023478424724, 'timeLeft': 837701544696, 
        #'structureShowInfoData': ['showinfo', 35832, 1023478424724], 'vulnerableTime': 9000000000}
        pass

    if not_type == 'StructureLostArmor':
        # same as StructureLostShields
        pass

    if not_type == 'StructureUnderAttack':
        # example:
        # {'allianceLinkData': ['showinfo', 16159, 498125261], 'shieldPercentage': 2.7245399818695597e-10, 'hullPercentage': 100.0, 
        # 'solarsystemID': 30001154, 'structureShowInfoData': ['showinfo', 35832, 1023478424724], 'corpLinkData': ['showinfo', 2, 98210135], 
        #'corpName': 'Infinite Point', 'structureID': 1023478424724, 'charID': 96554255, 'allianceID': 498125261, 
        #'armorPercentage': 99.95246052415511, 'allianceName': 'Test Alliance Please Ignore'}

        corpLinkData = not_data.get('corpLinkData')

        # to keep compatable with the general method later

        data['status'] = round(not_data.get('shieldPercentage'), 2), round(not_data.get('armorPercentage'), 2), round(not_data.get('hullPercentage'), 2)
        data['attacker_affiliations'] = _esihelpers.esi_affiliations(not_data.get('charID'))

    if not_type == 'TowerAlertMsg':
        # example:
        # {'moonID': 40139259, 'shieldValue': 0.9999255519999989, 'aggressorCorpID': 803493697, 'aggressorID': 90936488,
        #'solarSystemID': 30002185, 'aggressorAllianceID': 498125261, 'typeID': 16214, 'hullValue': 1.0, 'armorValue': 1.0}
        data['moon_info'] = _esihelpers.moon_info(not_data.get('moonID'))
        data['attacker_affiliations'] = _esihelpers.esi_affiliations(not_data.get('aggressorID'))
        data['status'] = round( 100 * not_data.get('shieldValue'), 2), 100, 100

    if not_type == 'SovCommandNodeEventStarted':
        # example:
        # {'constellationID': 20000347, 'solarSystemID': 30002365, 'campaignEventType': 1}
        data['campaign_typeid'] = not_data.get('campaignEventType')
        data['campaign_type'] = sov_campaigns(not_data.get('campaignEventType'))

    if not_type == 'EntosisCaptureStarted':
        # example:
        # {'solarSystemID': 30000744, 'structureTypeID': 21646}
        pass

    if not_type == 'SovStructureDestroyed':
        # example:
        # {'solarSystemID': 30000825, 'structureTypeID': 32226}
        pass

    # common things

    # structure info

    if not_data.get('structureShowInfoData') is not None:
        data['structure_type_data'] = _esihelpers.type_info(not_data.get('structureShowInfoData')[1])

    if not_data.get('structureTypeID') is not None:
        data['structure_type_data'] = _esihelpers.type_info(not_data.get('structureTypeID'))

    # structure ID for specific queries

    if not_data.get('structureID') is not None:
       data['structure_id'] = not_data.get('structureID')

       # fetch structure name
       request_url = 'universe/structures/{0}/'.format(data['structure_id'])
       code, result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

       data['structure_name'] = result.get('name')

       # can get solar system id from corplinkdata but whatever
       data['solar_system_info'] = _esihelpers.solar_system_info(result['solar_system_id'])

    # system info

    if not_data.get('solarSystemID') is not None:
        data['solar_system_info'] = _esihelpers.solar_system_info(not_data.get('solarSystemID'))

    return data

def filetime2epoch(ft):
    # fucking legacy code
    # thanks https://gist.github.com/Mostafa-Hamdy-Elgiar/9714475f1b3bc224ea063af81566d873

    EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
    HUNDREDS_OF_NANOSECONDS = 10000000
    return datetime.datetime.utcfromtimestamp((ft - EPOCH_AS_FILETIME) / HUNDREDS_OF_NANOSECONDS).timestamp()

def sov_campaigns(typeid):
    # eventType: Type of event this campaign is for. 1 = TCU defense, 2 = IHub defense, 3 = Station defense, 4 = Station Freeport.

    if typeid is 1:
        return 'TCU'

    if typeid is 2:
        return 'IHUB'

    return None

