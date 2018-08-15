import common.request_esi as _esi
import common.ldaphelpers as _ldaphelpers
import time
import redis
import sys
import re
import cgi
from common.logger import getlogger_new as getlogger

def maillist_forward(charid=None, mailing_list=None):

    logger = getlogger('ping_relay.mailing_lists')

    # setup redis

    r = redis.StrictRedis(host='localhost', port=6379, db=0)

    try:
        r.client_list()
    except redis.exceptions.ConnectionError as err:
        msg = 'redis connection error: {0}'.format(err)
        logger.error(msg)
    except redis.exceptions.ConnectionRefusedError as err:
        msg = 'redis connection error: {0}'.format(err)
        logger.error(msg)
    except Exception as err:
        msg = 'redis generic error: {0}'.format(err)
        logger.error(msg)

    # fetch mailing lists to confirm that the target is still valid

    request_url = 'characters/{0}/mail/lists/'.format(charid)

    code, result = _esi.esi(__name__, request_url, 'get', version='v1', charid=charid)

    if code != 200:
        # something broke severely
        msg = 'mailing list error: {0}'.format(result)
        logger.error(msg)
        # can't process without the ticker.
        return


    valid_list = False

    for item in result:
        if mailing_list == item.get('name'):
            valid_list = True
            valid_listid = item.get('mailing_list_id')

    if not valid_list:
        msg = 'character no longer subscribed to list {0}'.format(mailing_list)
        logger.error(msg)
        return

    # now that the mailing list id is known, character mails can be filtered

    request_url = 'characters/{0}/mail/'.format(charid)

    code, result = _esi.esi(__name__, request_url, 'get', version='v1', charid=charid)

    if code != 200:
        # something broke severely
        msg = 'mail endpoint error: {0}'.format(result)
        logger.error(msg)
        # can't process without the ticker.
        return

    fetch_mails = []

    cutoff = 0
    for mail in result:
        mail_id = mail.get('mail_id')
        recipients = mail.get('recipients')[0]

        # convert timestamp to epoch
        # example: 2018-05-08T17:30:00Z

        timestamp = time.strptime(mail.get('timestamp'), "%Y-%m-%dT%H:%M:%SZ")
        timestamp = time.mktime(timestamp)
        timestamp = int(timestamp)

        if recipients.get('recipient_id') == valid_listid and timestamp > cutoff:
            fetch_mails.append(mail_id)

    # parse mail
    # thx https://stackoverflow.com/questions/753052/strip-html-from-strings-in-python?utm_medium=organic&utm_source=google_rich_qa&utm_campaign=google_rich_qa
    tag_re = re.compile(r'(<!--.*?-->|<[^>]*>)')

    for mail in fetch_mails:
        request_url = 'characters/{0}/mail/{1}/'.format(charid, mail)

        code, result = _esi.esi(__name__, request_url, 'get', version='v1', charid=charid)

        if code != 200:
            # something broke severely
            msg = 'char {0} mail id {1} error: {2}'.format(charid, mail, result)
            logger.error(msg)
            # can't process without the ticker.
            continue

        subject = result.get('subject')
        body = tag_re.sub(' ', result.get('body'))

        timestamp = time.strptime(result.get('timestamp'), "%Y-%m-%dT%H:%M:%SZ")
        timestamp = time.mktime(timestamp)
        timestamp = int(timestamp)

        print(subject, timestamp, body)

maillist_forward(charid=1371703009, mailing_list='gc.mail')
