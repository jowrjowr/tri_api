import sys
import redis
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

def snoop():

    _logger.log('[' + __name__ + '] fetching notifications',_logger.LogLevel.INFO)

    charid=96863835

    char_notifications(charid)

def char_notifications(charid):

    # fetch notifications from an appropriately selected character

    # what kinds of notifications do we care about?

    alliance_notifications = [
        'EntosisCaptureStarted', 'SovCommandNodeEventStarted', 'SovStructureDestroyed',
        'SovStationEnteredFreeport', 'StationServiceDisabled',
    ]

    corp_notifications = [
        'StructureUnderAttack', 'StructureLostShields', 'StructureLostArmor', 'TowerAlertMsg',
    ]

    print('reeee')
    request_url = 'characters/{0}/notifications/'.format(charid)
    code, result = common.request_esi.esi(__name__, request_url, version='v2', charid=charid)

    if not code == 200:
        msg = 'characters/{0}/notifications error: {1}'.format(charid, result['error'])
        _logger.log('[' + __name__ + '] {0}'.format(msg),  _logger.LogLevel.WARNING)
        return None, None, None

    for item in result:
        not_type = item.get('type')
        if not_type == 'GameTimeReceived':
            print(item)

snoop()
