# programma leest een tabel met sonderingen in
# en bestanden met locaties van objecten (bruggen, kades)
# checkt of een sondering nabij een object is
# en kopieert het bestand naar een bestand met de naam [object]/[object]_S_[naam]

import geopandas as gpd
from shapely.geometry import Point
import re
import requests
from requests.structures import CaseInsensitiveDict
import json
from datetime import datetime
import xml.etree.ElementTree as ET

def haal_BRO(obj, objectBuffer, tests, geometries, gefType):
    broIds = []
    broGeoms = []
    # voeg BRO sonderingen toe
    if gefType == 'GEF-CPT':
        url = "https://publiek.broservices.nl/sr/cpt/v1/characteristics/searches"
    elif gefType == 'GEF-BORE':
        url =  "https://publiek.broservices.nl/sr/bhrgt/v2/characteristics/searches"

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"
    
    # maak een bounding box in lat, lon             
    objectBufferLatLon = gpd.GeoSeries(objectBuffer).set_crs("epsg:28992").to_crs("EPSG:4326")
    minx, miny, maxx, maxy = objectBufferLatLon[0].bounds

    # maak een request om mee te geven aan de url
    today = datetime.today().strftime('%Y-%m-%d')

    # beginDate mag niet te vroeg zijn 2017-01-01 werkt, 2008 niet
    dataBBdict = {"registrationPeriod": {"beginDate": "2017-01-01", "endDate": today}, "area": {"boundingBox": {"lowerCorner": {"lat": miny, "lon": minx}, "upperCorner": {"lat": maxy, "lon": maxx}}}}
    dataBB = json.dumps(dataBBdict)

    # doe de request
    resp = requests.post(url, headers=headers, data=dataBB)
    broResp = resp.content.decode("utf-8")
    root = ET.fromstring(broResp)

    for element in root.iter():
        if 'dispatchDocument' in element.tag:
            broId = False
            broGeom = False

            metadata = ({re.sub(r'{.*}', '', p.tag) : re.sub(r'\s*', '', p.text) for p in element.iter() if p.text is not None})

            broId = metadata['broId']
            
            for child in element.iter():
                if 'deliveredLocation' in child.tag:
                    locationData = ({re.sub(r'{.*}', '', p.tag) : re.sub(r'\s*', '', p.text) for p in element.iter() if p.text is not None})
                    coords = locationData['pos']
                    
                    broGeom = Point(float(coords[:int(len(coords)/2)]), float(coords[int(len(coords)/2):]))

            if type(broId) == str and type(broGeom) == Point:
                broIds.append(broId)
                broGeoms.append(broGeom)

    # maak een dataframe 
    broGDF = gpd.GeoDataFrame(columns=["test", "geometry"]).set_crs('epsg:28992')
    broGDF["test"] = broIds
    broGDF["geometry"] = broGeoms 

    # doorloop het dataframe
    for row in broGDF.itertuples():
        test = getattr(row, 'test')
        geometry = getattr(row, 'geometry')

        if geometry.within(objectBuffer):
            # download de xml-bestanden
            if gefType == 'GEF-CPT':
                url = f"https://publiek.broservices.nl/sr/cpt/v1/objects/{test}"
                print(url)
                resp = requests.get(url)

                # voeg de id en xy toe aan de grote lijst voor de kaarten
                tests.append(resp.content)
                geometries.append(geometry)

            elif gefType == 'GEF-BORE':
                for boreType in ['bhrgt']: # TODO: deze verwijderd, anders krijg je lege bestanden, zou gecheckt moeten worden 'bhrp', 'bhrg' 
                    url = f"https://publiek.broservices.nl/sr/{boreType}/v2/objects/{test}"
                    resp = requests.get(url)

                    # voeg de id en xy toe aan de grote lijst voor de kaarten
                    tests.append(resp.content)
                    geometries.append(geometry)
    return tests

