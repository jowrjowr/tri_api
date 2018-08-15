import json
import common.database as _database
import common.request_esi
import common.logger as _logger
import requests
import MySQLdb as mysql

def migratefailures():

    try:
        sql_conn = mysql.connect(
            database='forum',
            user='root',
            password='wua8e0.NR68qI',
            host=_database.DB_HOST)
    except mysql.Error as err:
        return False

    cursor = sql_conn.cursor()

    query = 'select name, failed_logins from forum.core_members'

    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        return False

    for charname, failed_logins in rows:

        if failed_logins == None or failed_logins == '[]':
            continue

        failures = json.loads(failed_logins)
        for ip_address in failures.keys():
            for date in failures[ip_address]:
                _logger.securitylog(__name__, 'forum login', charname=charname, ipaddress=ip_address, date=date, detail='invalid password')

migratefailures()
