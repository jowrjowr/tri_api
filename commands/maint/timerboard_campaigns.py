import common.request_esi as _esi
import common.ldaphelpers as _ldaphelpers
import common.esihelpers as _esihelpers
import common.logger as _logger
import common.database as _database
import redis
import time
import MySQLdb as mysql

def sov_campaigns(alliance_id):

    # fetch all the not-tcu sov campaigns for one alliance

    msg = 'fetching sovreignity campaigns for alliance {0}'.format(alliance_id)
    _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.DEBUG)

    url = 'sovereignty/campaigns/'
    code, result = _esi.esi(__name__, url, method='get', base='esi', version='v1')

    msg = 'sovreignity campaign return for alliance {0}: {1}'.format(alliance_id, result)
    _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.DEBUG)

    campaigns = dict()
    for campaign in result:

        info = dict()

        info['event'] = campaign.get('event_type')

        campaign_id = campaign.get('campaign_id')
        start_time = campaign.get('start_time')
        solar_system_id = campaign.get('solar_system_id')

        # only one alliance id at a time
        if not campaign.get('defender_id') == alliance_id:
            continue

        # do not give a shit about tcus, they literally do not matter
        if campaign.get('event_type') == 'tcu_defense':
            continue

        # do some more expensive info grabbing since these are important

        # get system info

        system_info = _esihelpers.solar_system_info(solar_system_id)

        if system_info['error']:
            msg = 'unable to retreive solar system information for {0}'.format(solar_system_id)
            _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.WARNING)
            continue
        else:
            info['system_info'] = system_info

        # cast the start time to epoch
        # example time: '2017-09-23T23:47:21Z'

        try:
            start_time = time.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
        except Exception as e:
            msg = 'unable to cast campaign id {0} start time {1} to epoch: {2}'.format(campaign_id, start_time, e)
            _logger.log('[' + __name__ + '] {}'.format(msg), _logger.LogLevel.WARNING)
            continue

        info['start_time'] = time.mktime(start_time)

        campaigns[campaign_id] = info

    return campaigns

def maint_timerboard_campaigns():
    # dump the sov campaigns into the timerboard

    ## setup connections
    # redis

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except redis.exceptions.ConnectionRefusedError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except Exception as err:
        logger.error('[' + __name__ + '] Redis generic error: ' + str(err))
    # mysql

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False


    alliance_id = 933731581
    campaigns = sov_campaigns(alliance_id)

    for campaign_id in campaigns.keys():

        campaign = campaigns[campaign_id]
        redis_key = 'campaign_{0}'.format(campaign_id)
        if r.get(redis_key) is not None:
            # already in redis thus already in mysql, we can skip this one.
            continue

        campaign_type = campaign['event']
        station_cycle = None

        if campaign_type == 'ihub_defense':
            sql_campaign_type = 'IHUB'
        if campaign_type == 'tcu_defense':
            sql_campaign_type = 'TCU'
        if campaign_type == 'station_defense':
            sql_campaign_type = 'STATION'
            station_cycle = 'INITIAL'

        cursor = sql_conn.cursor()

        query = 'INSERT INTO Timerboard (DateTime, System, Constellation, Region, Type, Friendly, Owner, StationCycle, PostedBy) '
        query += 'VALUES (FROM_UNIXTIME(%s), %s, %s, %s, %s, %s, %s, %s, %s)'

        try:
            cursor.execute(query, (
                campaign['start_time'],
                campaign['system_info']['solar_system_name'],
                campaign['system_info']['constellation_name'],
                campaign['system_info']['region_name'],
                sql_campaign_type,
                'FRIENDLY',
                'TRI',
                station_cycle,
                'Automatic',
            ),)
        except mysql.Error as err:
            msg = 'mysql error: {}'.format(err)
            _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
            return False
        finally:
            cursor.close()
            sql_conn.commit()

        # set a tag so we don't re-insert
        r.set(redis_key, 'yup')

    # done
    sql_conn.close()
