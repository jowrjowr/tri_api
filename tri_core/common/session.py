def makesession(charid):

    import common.logger as _logger
    import common.request_esi
    import common.credentials.core as _core
    import common.database as _database

    import base64
    import urllib.parse
    import phpserialize
    import MySQLdb as mysql
    import json
    import uuid
    import os
    import hmac
    import hashlib
    import time
    import redis

    from Crypto import Random
    from Crypto.Cipher import AES

    key = _core.key

    # construct the user's session. this is how you auth to core.
    # we're mimicing laravel structure exactly. it is finikiy.
    payload = dict()

    # actually useful data
    payload['charID'] = charid
    payload['csrf_token'] = uuid.uuid4().hex
    payload['_previous'] = dict()
    payload['_previous']['url'] = 'https://auth.triumvirate.rocks/eve/callback'
    payload['ip_address'] = ''
    payload['user_agent'] = ''

    # i have literally no idea what purpose this serves.

    payload['_flash'] = dict()
    payload['_flash']['new'] = ''
    payload['_flash']['old'] = ''

    # see: vendor/symfony/http-foundation/Session/Storage/MetadataBag.php
    # for why the _sf2_meta shit is here
    # c: create, u: updated, l: lifetime
    payload['_sf2_meta'] = dict()
    payload['_sf2_meta']['u'] = time.time()
    payload['_sf2_meta']['l'] = 0
    payload['_sf2_meta']['c'] = time.time()

    # first, get the user data.

    esi_url = 'characters/' + str(charid) + '/?datasource=tranquility'
    code, result = common.request_esi.esi(__name__, esi_url, 'get')
    _logger.log('[' + __name__ + '] /characters output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /characters API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        return False

    charname = result['name']
    payload['charName'] = charname
    payload['corpID'] = int(result['corporation_id'])
    payload['birthday'] = result['birthday']

    try:
        payload['allianceID'] = int(result['alliance_id'])
    except KeyError:
        # should never happen here!
        payload['allianceID'] = False
        payload['allianceName'] = 'Unknown'

    # the scope controls whether you are tri or a tri blue
    # this in turn controls various access levels

    # this is legacy code for laravel - python services determine access in different ways.

    if payload['allianceID'] == 933731581:
        # "tri alliance only" scope
        payload['scope'] = 2
    else:
        payload['scope'] = 1

    esi_url = 'corporations/' + str(payload['corpID']) + '/?datasource=tranquility'
    code, result = common.request_esi.esi(__name__, esi_url, 'get')
    _logger.log('[' + __name__ + '] /corporations output: {}'.format(result), _logger.LogLevel.DEBUG)

    if not code == 200:
        # something broke severely
        _logger.log('[' + __name__ + '] /corporations API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
        return False

    payload['corpName'] = result['corporation_name']

    if not payload['allianceID'] == False:
        esi_url = 'alliances/' + str(payload['allianceID']) + '/?datasource=tranquility'
        code, result = common.request_esi.esi(__name__, esi_url, 'get')
        _logger.log('[' + __name__ + '] /alliances output: {}'.format(result), _logger.LogLevel.DEBUG)

        if not code == 200:
            _logger.log('[' + __name__ + '] /alliances API error {0}: {1}'.format(code, result['error']), _logger.LogLevel.ERROR)
            return False
        payload['allianceName'] = result['alliance_name']
    else:
        payload['allianceName'] = None

    payload = phpserialize.dumps(payload)
    payload = base64.b64encode(payload)

    # AES requires inputs to be multiples of 16
    #
    # laravel seems exceedingly picky with the session id size and padding
    # so we're going to mimic it exactly

    sessionid = uuid.uuid4().hex + uuid.uuid4().hex
    sessionid = sessionid[:40]

    # feed the session data into the session table
    # mysql is just to make laravel happy

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    cursor = sql_conn.cursor()
    now = time.time()

    # make sure this is the only session. i would adjust table schema but that'd probably
    # break laravel
    # purge null sessions too
    try:
        query = 'DELETE FROM sessions WHERE charID = %s'
        cursor.execute(query, (charid,),)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    try:
        query = 'INSERT INTO sessions (id, charID, charName, payload, last_activity) VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(query, (
            sessionid,
            charid,
            charname,
            payload,
            now,
        ),)
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    finally:
        cursor.close()
        sql_conn.commit()
        sql_conn.close()

    # store the session id + payload into redis

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except redis.exceptions.ConnectionRefusedError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except Exception as err:
        logger.error('[' + __name__ + '] Redis generic error: ' + str(err))

    try:
        # store the session in redis and set it to timeout in a week
        r.set(sessionid, payload)
        expires = 86400 * 7 # 1 week
        r.expire(sessionid, expires)
    except Exception as err:
        _logger.log('[' + __name__ + '] Redis error: ' + str(err), _logger.LogLevel.ERROR)


    # construct the encrypted cookie contents, which consists of three things:
    # the initialization vector for AES, a sha256 hash, and the AES encrypted session id

    key = base64.b64decode(key)
    iv = uuid.uuid4().hex[:16] # need a 16 digit initial value for the encryption
    iv = iv.encode('utf-8')

    # structure the php serialized thing in a way that laravel likes
    # don't rock the boat

    sessionid = 's:40:"' + str(sessionid) + '";\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10'
    sessionid = sessionid.encode('utf-8')

    _logger.log('[' + __name__ + '] key length: {0}, iv length: {1}, sessionid length: {2}'.format(len(key),len(iv),len(sessionid)), _logger.LogLevel.DEBUG)

    # the madness as demanded by laravel
    # see: vendor/laravel/framework/src/Illuminate/Encryption/Encrypter.php

    try:
        value = AES.new(key, AES.MODE_CBC, iv).encrypt(sessionid)
    except Exception as error:
        # how this can happen with fixed lengths i'm unclear...
        _logger.log('[' + __name__ + '] AES error: ' + str(error), _logger.LogLevel.ERROR)
        return False

    value = base64.b64encode(value)
    iv = base64.b64encode(iv)

    hash = hmac.new(key, msg=iv + value, digestmod=hashlib.sha256)

    cookie = dict()
    cookie['mac'] = hash.hexdigest()
    cookie['iv'] = iv.decode('utf-8')
    cookie['value'] = value.decode('utf-8')

    cookie = json.dumps(cookie)
    cookie = base64.b64encode(cookie.encode('utf-8'))
    cookie = cookie.decode('utf-8')

    return cookie

def readsession(cookie):
    import common.logger as _logger
    import common.credentials.core as _core

    import phpserialize
    import hmac
    import hashlib
    import re
    import json
    import redis

    from phpserialize import loads as _phploads
    from base64 import b64encode, b64decode
    from Crypto import Random
    from Crypto.Cipher import AES

    # this is the same as makesession() but in reverse, basically

    key = b64decode(_core.key)

    # so a bit of decoding first, in reverse to makesession()
    # i can't for the life of me find the right decoding library for this...
    cookie = re.sub('%3(d|D)', '=', cookie)

    cookie = b64decode(cookie)
    cookie = cookie.decode('utf-8')
    cookie = json.loads(cookie)

    # validate the hash
    # the hash message format is what laravel uses. i would not do it quite this way normally.

    digest_msg = cookie['iv'].encode('utf-8') + cookie['value'].encode('utf-8')

    # the cookie object is the hex digest of the hmac
    calculated_digest = hmac.new(key, msg=digest_msg, digestmod=hashlib.sha256).hexdigest()
    cookie_digest = cookie['mac']

    if not calculated_digest == cookie_digest:
        return False

    # from here onwards the contents of the cookie can be absolutely trusted as coming from
    # us, as the contents are shas256 hashed (and checked) as well as being aes encrypted

    iv = b64decode(cookie['iv'])
    value = b64decode(cookie['value'])

    # decrypt the value object into the session key

    try:
        aes = AES.new(key, AES.MODE_CBC, iv)
        session = aes.decrypt(value)
        session = phpserialize.loads(session)
        session = session.decode('utf-8')
    except Exception as error:
        _logger.log('[' + __name__ + '] unable to decrypt & unserialize session data: ' + str(err), _logger.LogLevel.WARNING)
        return False

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except redis.exceptions.ConnectionRefusedError as err:
        _logger.log('[' + __name__ + '] Redis connection error: ' + str(err), _logger.LogLevel.ERROR)
    except Exception as err:
        _logger.log('[' + __name__ + '] Redis generic error: ' + str(err), _logger.LogLevel.ERROR)

    # retrieve the payload from the redis store

    payload = r.get(session)

    if payload == None:
        _logger.log('[' + __name__ + '] unable to retrive session data', _logger.LogLevel.ERROR)
        return False

    # dismantle the payload

    payload = b64decode(payload)
    payload = _phploads(payload, decode_strings=True)

    return payload

