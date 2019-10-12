# Load polling stations data from Ukrainian State Voters Registry
# through SOAP protocol.

from zeep import Client
from zeep.wsdl.bindings.soap import Soap12Binding
import json
import os
import logging

SAVE_PRECISON = 5


# Headers fix from
# https://gist.github.com/alexshpilkin/e45422181a34d76a293ac03c14164530
def _set_http_headers(self, serialized, operation):
    serialized.headers['Content-Type'] = '; '.join(
        ['application/soap+xml', 'charset=utf-8'] +
        (['action="%s"' % operation.soapaction]
         if operation.soapaction is not None
         else []))

Soap12Binding._set_http_headers = _set_http_headers


def _set_http_headers(self, serialized, operation):
    serialized.headers['Content-Type'] = '; '.join(
        ['application/soap+xml', 'charset=utf-8'] +
        (['action="%s"' % operation.soapaction]
         if operation.soapaction is not None else [])
    )


soap = Client('config/drv.wsdl')

query = soap.bind('GetPSService', 'PSPort')

keys = [
    'PS_Area', 'PS_CommissionAdr', 'PS_CommissionLocation', 'PS_Desc',
    'PS_GeoDVK', 'PS_GeoData', 'PS_GeoPG', 'PS_Num', 'PS_PlaceVotingAdr',
    'PS_PlaceVotingLocation', 'PS_Size', 'PS_Type', 'Region_Id'
]
geokeys = {'PS_GeoDVK', 'PS_GeoData', 'PS_GeoPG'}


def mapper(entry, key, geokeys):
    """
    Extract the necessary output from a data record from the server response
    :param entry: data record (one polling station)
    :param key: field to be process
    :param geokeys: set of keys with GeoJSON data
    :return: extracted value
    """
    if key in geokeys:
        if entry[key]:
            loaded = json.loads(entry[key])
            coordinates = loaded['coordinates']
            if loaded['type'] == 'Polygon':
                # reduce precision of GeoJSON coordinates
                coordinates = [
                    [[round(c[0], SAVE_PRECISON), round(c[1], SAVE_PRECISON)]
                     for c in a] for a in coordinates
                ]
            elif loaded['type'] == 'MultiPolygon':
                coordinates = [
                    [[[round(c[0], SAVE_PRECISON), round(c[1], SAVE_PRECISON)]
                      for c in a] for a in polygon] for polygon in coordinates
                ]
            else:
                coordinates = [
                    round(coordinates[0], SAVE_PRECISON),
                    round(coordinates[1], SAVE_PRECISON)
                ]
            return json.dumps(coordinates)
        else:
            return ''
    else:
        return entry[key]


def load_stations_from_register(local_data_folder):
    """
    Loads all information from the State Voters Register and saves
    to multiple files locally (one file per voters district).
    :param local_data_folder: folder to save files locally
    :return:
    """
    for n in range(1, 227):
        res = query.PSQuery({'Area': n})
        res2 = [
            {k.lower(): mapper(e, k, geokeys) for k in keys}
            for e in res['PollingStation']
        ]
        with open(
                os.path.join(local_data_folder, f'stations_{n}.json'), 'w'
        ) as f:
            for line in res2:
                f.write(f'{json.dumps(line, ensure_ascii=False)}\n')
        logging.info(f'Loaded polling stations info for district {n}')
