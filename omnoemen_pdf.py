# programma leest een tabel met sonderingen in
# en bestanden met locaties van objecten (bruggen, kades)
# checkt of een sondering nabij een object is
# en kopieert het bestand naar een bestand met de naam [object]/[object]_S_[naam]

import pandas as pd
import geopandas as gpd
import shutil
import os
import matplotlib.pyplot as plt
import contextily as cx
from shapely.geometry import Polygon, Point, LineString
import re
import pandas as pd
import requests
from requests.structures import CaseInsensitiveDict
import json
import folium
from datetime import datetime
from xml.etree.ElementTree import ElementTree
import xml.etree.ElementTree as ET

bufferKlein = 100 # voor kades
bufferGroot = 30 # voor bruggen

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
                for boreType in ['bhrgt', 'bhrp', 'bhrg']:
                    url = f"https://publiek.broservices.nl/sr/{boreType}/v2/objects/{test}"
                    resp = requests.get(url)

                    # voeg de id en xy toe aan de grote lijst voor de kaarten
                    tests.append(resp.content)
                    geometries.append(geometry)
    return tests

def maak_interactieve_webkaart(obj, outputGDF):
    # maak een interactieve webkaart
    map = folium.Map(location = [52.35, 4.9], tiles = "OpenStreetMap", zoom_start = 13)

    # zet de RD-coordinaten om naar LatLon
    outputGDF = outputGDF.to_crs("EPSG:4326")

    # maak markers met popup
    for row in outputGDF.itertuples():
        geometry = getattr(row, "geometry")
        coordinates = [geometry.xy[1][0], geometry.xy[0][0]]
        test = getattr(row, "test")
        image = f"{obj}_S_{test.split('.')[0]}.png"
        map.add_child(folium.Marker(location=coordinates, popup=folium.Popup(html=f"<strong>{test}</strong><br><img src='{image}' width='300'>", sticky=True)))
    map.save(f'./omgenoemd/{obj}/{obj}.html')

def maak_shape(obj, outputGDF):
    # maak een shape
    if len(outputGDF) > 0:
        outputGDF.to_file(f'./omgenoemd/{obj}/{obj}.shp')

def maak_png(obj, outputGDF, objectData):
    fig, ax = plt.subplots(figsize=(16, 12))
    outputGDF.plot(ax=ax)

    # voeg de brug of kade toe aan de plot
    # bij gebruik van een rechthoek is die min of meer gelijk aan de rand van de plot
    # een rechthoek op deze manier plotten, levert een grote rode gevulde rechthoek
    objectData["geometry"].plot(ax=ax, color="r", edgecolor="r", facecolor=None)

    for row in outputGDF.itertuples():
        test = getattr(row, 'test')
        x = getattr(row, 'geometry').x
        y = getattr(row, 'geometry').y
        ax.annotate(test, [x,y])
    cx.add_basemap(ax, crs=outputGDF.crs.to_string(), source=cx.providers.Stamen.TonerLite)
    plt.title(obj)
    plt.tight_layout()
    # TODO: verschillende kleuren voor gevonden / niet gevonden? vormen voor gef /pdf?
    fig.savefig(f'./omgenoemd/{obj}/{obj}.png')

def haal_omegam(obj, objectBuffer, ext, omegamMap, tests, geometries, gefType):
    # verwerk de omegam sonderingen
    omegamObject = gpd.GeoDataFrame()
    omegamObject = omegamObject.append(omegam[omegam.geometry.within(objectBuffer)])
    
    for row in omegamObject.itertuples():
        gefType = getattr(row, 'GEF_Type')
        if gefType == 'GEF-CPT':

            vak = f"VAK_{getattr(row, 'FileID').split('-')[0]}"
            test = getattr(row, 'FileID').split('.')[0]
            
            source = f'{omegamMap}/{vak}/{test}.{ext}'
            destination = f'./omgenoemd/{obj}/{obj}_S_{test}.{ext}'
            try:
                shutil.copy(source, destination)
            except:
                print(f'{source} niet gevonden')

        tests.append(test)
        geometries.append(row.geometry)

def haal_niet_omegam(obj, objectBuffer, nietomegamMap, ext, Ext, filetype, tests, geometries):
    # verwerk de niet-omegam sonderingen
    nietOmegamObject = gpd.GeoDataFrame()
    nietOmegamObject = nietOmegamObject.append(nietOmegam[nietOmegam.geometry.within(objectBuffer)])

    # dit is waarschijnlijk erg langzaam omdat steeds de hele map doorlopen wordt
    # er is vast een mooiere oplossing, maar dit was snel genoeg
    for row in nietOmegamObject.itertuples():
        for root, dirs, files in os.walk(nietomegamMap):
            for name in files:
                if name.lower().endswith(f'{getattr(row, "FileID").split(".")[0]}.{ext}'):
                    test = getattr(row, 'TestID')
                    try:
                        if filetype == 'gef':
                            source = f'{root}/{name}'
                        if filetype == 'pdf':
                            source = f'{root}/{name}.{ext}'
                        destination = f'./omgenoemd/{obj}/{obj}_S_{test}.{ext}'
                        shutil.copy(source, destination)
                    except:
                        try: 
                            if filetype == 'gef':
                                source = f'{root}/{name}' # TODO: dit is dubbelop, is hier geen extensie nodig?
                            if filetype == 'pdf':
                                source = f'{root}/{name}.{Ext}'
                            destination = f'./omgenoemd/{obj}/{obj}_S_{test}.{Ext}'
                            shutil.copy(source, destination)
                        except:
                            try:
                                if filetype == 'gef':
                                    source = f'{root}/{name}'
                                if filetype == 'pdf':
                                    source = f'{root}/{name}.{ext}'
                                test = name.replace('.gef', '')
                                test = name.replace('.GEF', '')
                                print(test)
                                destination = f'./omgenoemd/{obj}/{obj}_S_{test}.{ext}'
                                shutil.copy(source, destination)
                            except Exception as e:
                                print(e)

                    tests.append(test)
                    geometries.append(row.geometry)


def haal_waternet(obj, ext, waternet, objectBuffer, omegamMap, tests, geometries):
    # verwerk de waternet sonderingen
    # TODO: het overgrote deel is met de vakken, een klein deel met projectnummers
    # TODO: die met projectnummers worden niet meegenomen. Makkelijkste eerst een check op vinden met vak als niet lukt dan zoals nietOmegam
    # TODO: het Waternet archief wordt nog een keer aangeleverd (BRO-overleg januari 2022) 
    waternetObject = gpd.GeoDataFrame()
    waternetObject = waternetObject.append(waternet[waternet.geometry.within(objectBuffer)])
    
    for row in waternetObject.itertuples():

        vak = f"VAK_{getattr(row, 'GGNIDENT').split('-')[0]}"
        test = getattr(row, 'GGNIDENT')
        
        source = f'{omegamMap}/{vak}/{test}.{ext}'
        destination = f'./omgenoemd/{obj}/{obj}_S_{test}.{ext}'
        try:
            shutil.copy(source, destination)
        except:
            print(f'{source} niet gevonden')

        tests.append(test)
        geometries.append(row.geometry)

def haal_persoonlijke_archieven(obj, objectBuffer, filetype, persArchiefMap, tests, geometries):
    # verwerk persoonlijke archieven
    # hierin zitten alleen GEF, geen pdf
    if filetype == 'gef':
        persArchiefObject = gpd.GeoDataFrame()
        persArchiefObject = persArchiefObject.append(persArchief[persArchief.geometry.within(objectBuffer)])
        
        for row in persArchiefObject.itertuples():
            test = getattr(row, "test")

            source = f'{persArchiefMap}/{test}'
            destination = f'./omgenoemd/{obj}/{obj}_S_{test}'
            try:
                if not os.path.isdir(f'./omgenoemd/{obj}'):
                    os.mkdir(f'./omgenoemd/{obj}')
                shutil.copy(source, destination)
            except:
                print(f'{source} niet gevonden')

            tests.append(test)
            geometries.append(row.geometry)


def kopieer_bestanden(objecttypes, bestandstypes, omegam, nietOmegam, waternetSonderingen, waternetBoringen, selectie, buffer, inclBRO = False):

    for objectType in objecttypes:
        column = "KUNSTWERKN"
        # TODO: opruimen, dit is nog rommelig, maar het moet om kunnen gaan met allerlei opties
        if objectType not in ["bruggen", "kades"]:
            objecten = [objectType]
            if type(buffer) == list: # dan is het een bounding box
                geometry = Polygon(((buffer[0], buffer[1]), (buffer[2], buffer[1]), (buffer[2], buffer[3]), (buffer[0], buffer[3])))
                objectDF = pd.DataFrame().from_dict({"KUNSTWERKN": [objectType], "geometry": [geometry]})
                objectGDF = gpd.GeoDataFrame(objectDF).set_crs('epsg:28992')
                buffer = 0
            else:
                # dit gebruik je om zelf opties in te stellen
                lijnFromFile = False
                lijnFromCoords = False
                lijnen = False
                punt = False

                # dit voor een lijn in een bestand
                if lijnFromFile:
                    objectGDF = gpd.read_file('./bestand.geojson') # TODO: dit moet een variabele zijn
                    objecten = objectGDF["KUNSTWERKN"]

                if lijnFromCoords:
                    # hier zelf coordinaten invoeren
                    geometry = LineString([(121946.01,487595.66), (121848.41,487305.51), (121564.89,486838.07)])
                    objectDF = pd.DataFrame().from_dict({"KUNSTWERKN": [objectType], "geometry": [geometry]})
                    objectGDF = gpd.GeoDataFrame(objectDF).set_crs('epsg:28992')
                    objecten = objectGDF["KUNSTWERKN"]

                # dit voor een punt
                if punt:
                    geometry = Point(119347, 487803)
                    objectDF = pd.DataFrame().from_dict({"KUNSTWERKN": [objectType], "geometry": [geometry]})
                    objectGDF = gpd.GeoDataFrame(objectDF).set_crs('epsg:28992')
                    objecten = objectGDF["KUNSTWERKN"]
             
                if lijnen:
                    objectGDF = gpd.read_file('Rijbanen_asfalt_Noord_landelijk_lijnen.geojson')
                    column = "fid"
                    objecten = objectGDF[column]
        else:
            if objectType == "bruggen":
                objectGDF = gpd.read_file("../../data/GIS/Brugnummers/overbruggingsdeelkunstwerk_point.geojson")

            if objectType == "kades":
                objectGDF = gpd.read_file("../../data/GIS/Kademuren/Kade Kunstwerk_20191007.geojson") # code loopt vast op de shp

            if selectie == None:
                objecten = objectGDF["KUNSTWERKN"]
            else:
                objecten = selectie

        print(f"start {objectType}")

        for obj in objecten:
            print(f'start {obj}')

            objectData = objectGDF[objectGDF[column] == obj]
            objectBuffer = objectData.buffer(buffer).unary_union
            if objectData['geometry'].length.iloc[0] > 10 or objectType == "bruggen": # in Noord waren veel kleine stukjes

                # maak een mapje
                if not os.path.isdir(f'./omgenoemd/{obj}'):
                    os.mkdir(f'./omgenoemd/{obj}')

                outputGDF = gpd.GeoDataFrame(columns=["test", "geometry"]).set_crs('epsg:28992')
                tests = []
                geometries = []

                gefType = 'GEF-CPT'
                directory = 'cpt'

                for filetype in bestandstypes:
                    if filetype == 'pdf':
                        omegamMap = f'../../data/{directory}/PDF/omegam'
                        nietomegamMap = f'../../data/{directory}/PDF/niet_omegam'
                        ext = 'pdf'
                        Ext = 'PDF'

                    if filetype == 'gef':
                        omegamMap = f'../../data/{directory}/GEF/omegam'
                        nietomegamMap = f'../../data/{directory}/GEF/niet_omegam'
                        persArchiefMap = f'../../data/{directory}/GEF_omnoemen'
                        ext = 'gef'
                        Ext = 'GEF'

                    haal_niet_omegam(obj, objectBuffer, nietomegamMap, ext, Ext, filetype, tests, geometries)
                    haal_omegam(obj, objectBuffer, ext, omegamMap, tests, geometries, gefType)
                    # de map "persoonlijke archieven" bestaat niet meer
#                    haal_persoonlijke_archieven(obj, objectBuffer, filetype, persArchiefMap, tests, geometries)
                    haal_waternet(obj, ext, waternetSonderingen, objectBuffer, omegamMap, tests, geometries)
                    if inclBRO:
                        haal_BRO(obj, objectBuffer, tests, geometries, gefType)

                gefType = 'GEF-BORE'
                omegamMap = f'../../data/{directory}/GEF/omegam'
                haal_omegam(obj, objectBuffer, ext, omegamMap, tests, geometries, gefType)
                if inclBRO:
                    haal_BRO(obj, objectBuffer, tests, geometries, gefType) 
                haal_waternet(obj, ext, waternetBoringen, objectBuffer, omegamMap, tests, geometries)

                outputGDF["test"] = tests
                outputGDF["geometry"] = geometries

                maak_shape(obj, outputGDF)
#               maak_png(obj, outputGDF, objectData)
                maak_interactieve_webkaart(obj, outputGDF)

                if len(outputGDF) < 1:
                    shutil.rmtree(f'./omgenoemd/{obj}')

selectie = ["HGG0103", "DCG0101", "DCG0201", "DCG0202", "DCG0301", "DCG0302", "DCG0401", "DCG0402", "DCG0501", "DCG0502", "JLK0102", "DCG0102", "HGG0102"] # DCK
selectie = ["KBW0202"]
bestandstypes = ["gef", "pdf"] # "gef", "pdf"

objecttypes = ["Noord"] # "bruggen", "kades" of iets anders

# voor Peer
selectie = ["WKN0104", "ZKG0102"]
objecttypes = ["kades"]

# voor Aziz
selectie = ["AMS1101", "AMS1012", "OEV1849", "OEV0386", "OEV0387", "OEV0504"]
objecttypes = ["kades"]

buffer = 10 # kan ook gebruikt worden voor rechthoek [xmin, ymin, xmax, ymax] 

# voor Barbara Berkhout
selectie = ["BRU0110", "BRU0057", "BRU0059", "BRU0061", "BRU0062"]
objecttypes = ["bruggen"]
buffer = 50

# zeeburgereiland voor Fugro 3D-model
bestandstypes = ["gef"]
buffer = [125553.6, 486163.1, 127391.6, 488150.7]
objecttypes = ["ZBE"]

# gerbrandypark voor Julius
bestandstypes = ["gef", "pdf"]
buffer = [116597.59,487784.60, 117532.57,487966.53]
objecttypes = ["gerbrandypark"]

# wallen Oude Waal
bestandstypes = ["gef"]
selectie = ["WEG0201"]
objecttypes = ["kades"]
buffer = 25
inclBRO = True

# wallen Gelderse kade - Kloveniersburgwal (doorsnede hele gebied)
bestandstypes = ["gef"]
selectie = ["WEG0201"]
objecttypes = ["WallenNNOZZW"]
buffer = 30
inclBRO = True

# Oudezijds kolk
bestandstypes = ["gef", "pdf"] # TODO: pdf werkt niet, want die kijkt ook in de gef map
selectie = ["OZK0101"]
objecttypes = ["kades"]
buffer = 30
inclBRO = True

# oudezijds achterburgwal
bestandstypes = ["gef"] 
selectie = ["OAW0201", "OAW0301", "OAW0401", "OAW0501", "OAW0601", "OAW0701"] # TODO: "OAW0101", geeft een foutmelding
objecttypes = ["kades"]
buffer = 20
inclBRO = True

bestandstypes = ["gef"] 
selectie = ["OVW0101", "OVW0201", "OVW0301", "OVW0401", "OVW0501", "OVW0601", "OVW0701", "OVW0801"] 
objecttypes = ["kades"]
buffer = 20
inclBRO = True

bestandstypes = ["gef"] 
selectie = ["WEG0101", "WEG0201", "WEG0102", "WEG0202"] 
objecttypes = ["kades"]
buffer = 20
inclBRO = True


bestandstypes = ["gef"] 
selectie = ["PRG0101", "PRG0201", "PRG0301"] 
objecttypes = ["kades"]
buffer = 20
inclBRO = True

if __name__ == '__main__':
    kopieer_bestanden(objecttypes, bestandstypes, omegam, nietOmegam, waternetSonderingen, waternetBoringen, selectie, buffer, inclBRO)

