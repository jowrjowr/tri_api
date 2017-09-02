from flask import request, Response, json
from tri_api import app

import common.logger as _logger
import redis

# what the vote can be

vote_classes = [ 'supers', 'titans', 'dreads', 'fax', 'carriers' ]

@app.route('/core/fleets/active/<int:fleet_id>/vote', methods=['GET'])
def fleet_vote(fleet_id):

    # get the fleet composition voting results

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    ipaddress = request.headers['X-Real-Ip']
    log_charid = request.args.get('log_charid')
    _logger.securitylog(__name__, 'retrieved fleet vote', detail='fleet {0}'.format(fleet_id), ipaddress=ipaddress, charid=log_charid)

    # redis does not actually connect above, i have to specifically test

    error = False
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        msg = 'Redis connection error: {0}'.format(err)
        error = True
    except redis.exceptions.ConnectionRefusedError as err:
        msg = 'Redis server offline'
        error = True
    except Exception as err:
        msg = 'Redis generic error: {0}'.format(err)
        error = True

    if error:
        _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
        js = json.dumps({'error': msg})
        return Response(js, status=500, mimetype='application/json')

    # build the data structure back

    result = dict()

    for ship_class in vote_classes:

        # fetch the redis amount
        try:
            amount = r.get('{0}:vote:{1}'.format(fleet_id, ship_class))
        except Exception as e:
            msg = 'error fetching vote amounts from redis'
            js = json.dumps({'error': msg})
            return Response(js, status=500, mimetype='application/json')

        if not amount:
            amount = 0

        result[ship_class] = int(amount)

    js = json.dumps(result)
    return Response(js, status=200, mimetype='application/json')

@app.route('/core/fleets/active/<int:fleet_id>/vote/<int:char_id>/', methods=['GET', 'POST'])
def fleet_char_vote(fleet_id, char_id):

    # get the fleet composition voting results from a specific character

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    ipaddress = request.headers['X-Real-Ip']

    # redis does not actually connect above, i have to specifically test

    error = False
    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        msg = 'Redis connection error: {0}'.format(err)
        error = True
    except redis.exceptions.ConnectionRefusedError as err:
        msg = 'Redis server offline'
        error = True
    except Exception as err:
        msg = 'Redis generic error: {0}'.format(err)
        error = True

    if error:
        _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
        js = json.dumps({'error': msg})
        return Response(js, status=500, mimetype='application/json')

    if request.method == 'GET':

        # build the data structure back

        result = dict()

        for ship_class in vote_classes:

            # fetch the redis amount
            try:
                amount = r.get('{0}:vote:{1}:{2}'.format(fleet_id, char_id, ship_class))
            except Exception as e:
                msg = 'error fetching vote amounts from redis: {0}'.format(e)
                _logger.log('[' + __name__ + '] {0}'.format(msg), _logger.LogLevel.ERROR)
                js = json.dumps({'error': msg})
                return Response(js, status=500, mimetype='application/json')
            if not amount:
                amount = 0

            result[ship_class] = int(amount)

        js = json.dumps(result)
        return Response(js, status=200, mimetype='application/json')
    elif request.method == 'POST':

        # *barf* i made a paplink
        _logger.securitylog(__name__, 'voted fleet composition', detail='fleet {0}'.format(fleet_id), ipaddress=ipaddress, charid=char_id)

        for ship_class in vote_classes:
            new_amount = request.values.get(ship_class)
            if not new_amount:
                new_amount = 0

            new_amount = int(new_amount)

            # first set the character vote and overall vote to zero if no keys exist
            r.setnx('{0}:vote:{1}:{2}'.format(fleet_id, char_id, ship_class), 0)
            r.setnx('{0}:vote:{1}'.format(fleet_id, ship_class), 0)

            if new_amount == 0:
                continue

            # get the current value just in case

            current_amount = r.get('{0}:vote:{1}:{2}'.format(fleet_id, char_id, ship_class))
            current_amount = current_amount.decode('utf-8')

            if not current_amount:
                current_amount = 0
            current_amount = int(current_amount)

            # next, we want to either increment or decrement

            if new_amount < 0:
                # decrement?
                # cap the amount a user can peel off the overall vote to be no more
                # than what they are already contributing

                new_amount = min(current_amount, abs(new_amount))

                if new_amount == 0:
                    # do nothing
                    continue

                # peel off the amount from what the user has, and the overall vote
                r.decr('{0}:vote:{1}'.format(fleet_id, ship_class), new_amount)
                r.decr('{0}:vote:{1}:{2}'.format(fleet_id, char_id, ship_class), new_amount)

            else:
                # increment
                r.incr('{0}:vote:{1}'.format(fleet_id, ship_class), new_amount)
                r.incr('{0}:vote:{1}:{2}'.format(fleet_id, char_id, ship_class), new_amount)

        js = json.dumps({})
        return Response(js, status=200, mimetype='application/json')

