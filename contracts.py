import common.esihelpers as _esihelpers
import common.request_esi
from concurrent.futures import ThreadPoolExecutor, as_completed
import resource

def contracts(region_id):

    if region_id > 11000000:
        # don't touch wormholes
        return

    request_url = 'universe/regions/{}/'.format(region_id)
    code, result = common.request_esi.esi(__name__, request_url, version='v1')

    region_name = result.get('name')

    # fetch all contracts out of a region

    request_url = 'contracts/public/{}/'.format(region_id)
    code, result = common.request_esi.esi(__name__, request_url, version='v1')

    contract_count = len(result)

    print('{0} contracts in region {1} - {2}'.format(contract_count, region_name, region_id))


    with ThreadPoolExecutor(40) as executor:
        futures = { executor.submit(contract_process, contract): contract for contract in result }
        for future in as_completed(futures):
            data = future.result()

def contract_process(contract):

    contract_type = contract['type']
    contract_id = contract['contract_id']

    titans = {
        11567: 'Avatar',
        671: 'Erebus',
        45649: 'Komodo',
        3764: 'Leviathan',
        42241: 'Molok',
        23773: 'Ragnarok',
    }
    supers = {
        23919: 'Aeon',
        22852: 'Hel',
        23913: 'Nyx',
        3514: 'Revenant',
        42125: 'Vendetta',
        23917: 'Wyvern'
    }


    if contract_type == 'courier':
        collateral = contract['collateral']

        if collateral < 1000000:
            #print(contract)
            pass
    elif contract_type == 'auction':
        # dont care
        pass

    else:

        # fetch price and scale to 1b

        price = contract['price'] / 1000000000

        request_url = 'contracts/public/items/{}/'.format(contract_id)
        code, result = common.request_esi.esi(__name__, request_url, version='v1')
        for item in result:
            type_id = item['type_id']

            if type_id in supers.keys():
                print(supers[type_id], price)
                if price < 10:
                    print(contract)
            elif type_id in titans.keys():
                print(titans[type_id], price)
                if price < 10:
                    print(contract)


def main():

    # fix open file limitations

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (25000, 75000))
    except Exception as e:
        logger.warn('unable to set nofile rlimit: {0}'.format(e))
        pass

    # fetch all regions

    request_url = 'universe/regions/'
    code, regions = common.request_esi.esi(__name__, request_url, version='v1')
#    contracts(10000016)
    for region in regions:
        contracts(region)
#x        return


main()

