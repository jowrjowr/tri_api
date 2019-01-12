import MySQLdb as mysql
import math
import numpy
from itertools import permutations, product
import common.database as _database

def bullshit():

    try:
        sql_conn = mysql.connect(
            database='sde',
            user='root',
            password='lskdjflaksdjflaksjdf',
            host=_database.DB_HOST)
    except mysql.Error as err:
        print(err)
        return False

    cursor = sql_conn.cursor()
    query = 'select solarSystemName, solarSystemID, x, y, z from mapSolarSystems where security < 0 and regionID < 11000000'

    try:
        rowcount = cursor.execute(query)
        rows = cursor.fetchall()
    except mysql.Error as err:
        print(err)
        return False
    # old blacklist table

    data = dict()

    for row in rows:

        sys_name, sys_id, x, y, z = row

        data[sys_id] = { 'name': sys_name, 'id': sys_id, 'xyz': (x, y, z) }

    systems = list(data.keys())

    jumprange = 7
    margin = 0.001
    for system in product(systems, systems):

        s1, s2 = system

        # no self-self permutations pls
        if s1 == s2:
            continue

        a = numpy.array(data[s1]['xyz'])
        b = numpy.array(data[s2]['xyz'])

        r = numpy.linalg.norm(a-b) / 86400*365.25*299792458
        if r < jumprange + margin  and r > jumprange - margin:
            print(r)
bullshit()
