def audit_discordmembers(range):

    import common.logger as _logger
    import common.database as _database
    import common.ldaphelpers as _ldaphelpers
    from common.discord_api import discord_members
    import MySQLdb as mysql
    import re
    import time
    import csv
    from maxminddb import open_database

    _logger.log('[' + __name__ + '] auditing CORE security log over {0} days, for specified targets'.format(range),_logger.LogLevel.INFO)

    try:
        sql_conn = mysql.connect(
            database=_database.DB_DATABASE,
            user=_database.DB_USERNAME,
            password=_database.DB_PASSWORD,
            host=_database.DB_HOST)
        cursor = sql_conn.cursor()
    except mysql.Error as err:
        _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
        return False
    geo_asn = open_database('/opt/geoip/GeoLite2-ASN.mmdb')
    geo_city = open_database('/opt/geoip/GeoLite2-City.mmdb')
    geo_country = open_database('/opt/geoip/GeoLite2-Country.mmdb')

    # prep the csv
    file = open('userdetails.csv', 'w', newline='')
    file.truncate()
    csvwriter = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    csvwriter.writerow(['charName', 'charID', 'ip address', 'Country', 'City'])


    # fetch the last week's security log stuff

    time_range = time.time() - 86400*range

    members = discord_members(__name__, 'tri_administration')
    skip = [ None, 'Sovereign' ]
    for member in members:
        # skip irrelevant
        if member in skip: continue

        # split off the tag and trim leading space
        tag, charname = member.split(']')
        charname = re.sub(r'^ ', '', charname)

        # map the character name to the ldap object

        charid = _ldaphelpers.ldap_name2id(__name__, charname)

        try:
            charid = charid['uid']
        except Exception as e:
            # character can't be mapped to a uid
            continue
        cursor = sql_conn.cursor()

        query = 'SELECT date, IP, action FROM Security WHERE date > FROM_UNIXTIME(%s) AND charID = %s'
        try:
            cursor.execute(query, (time_range, charid))
            rows = cursor.fetchall()
        except mysql.Error as err:
            _logger.log('[' + __name__ + '] mysql error: ' + str(err), _logger.LogLevel.ERROR)
            return
        finally:
            cursor.close()

        ips = set()
        for date, IP, action in rows:
            # 10.0.0.1 gets picked up from api stuff
            if IP == '10.0.0.1': continue
            ips.add(IP)

        ip_details = dict()

        for address in list(ips):
            details = dict()
            match_country = geo_country.get(address)
            match_city = geo_city.get(address)
            try:
                details['country'] = match_country['country']['iso_code']
            except Exception as e:
                details['country'] = 'Unknown'
            try:
                details['city'] = match_city['city']['names']['en']
            except Exception as e:
                details['city'] = 'Unknown'
            ip_details[address] = details

        for ip in ip_details:
            city = ip_details[ip]['city']
            country = ip_details[ip]['country']

            # spit out into csv
            csvwriter.writerow([charname, charid, ip, city, country])

    file.close()

    sql_conn.close()
    geo_asn.close()
    geo_city.close()
    geo_country.close()

    return

audit_discordmembers(30)
