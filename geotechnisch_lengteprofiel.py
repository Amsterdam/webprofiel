"""
Script om geotechnische lengteprofielen te tekenen
Geschreven door Thomas van der Linden, Ingenieursbureau Amsterdam

Input:
- sonderingen, als XML of GEF in een map met de naam cpts in dezelfde directory als de code
- profiellijn, als geojson bestand
- lagen, als excel tabel met de naam layers.xlsx in dezelfde directory als de code
    de tabel heeft kolommen laag (nummer in dezelfde volgorde als je getekend hebt), materiaal, kleur (kleurnamen in het Engels)

Output:
- output.geo dat ingelezen kan worden in de D-Serie # TODO: materialen toevoegen
- gtl.png en gtl.svg figuren met het geotechnisch lengteprofiel

Het programma opent een venster waarin geklikt kan worden om lijnen op te geven
Een klik met de linker muisknop voegt een punt toe aan de lijn (grens)
Een klik met de rechter muisknop creëert een nieuwe lijn (grens)
Sluit het venster af met de knop Quit, anders blijft het programma lopen en wordt er geen output gemaakt

Afhankelijkheden
- cpt_reader geschreven door Thomas van der Linden 
- standaard Python packages
"""

__author__ = "Thomas van der Linden"
__credits__ = ""
__license__ = "MPL-2.0"
__version__ = ""
__maintainer__ = "Thomas van der Linden"
__email__ = "t.van.der.linden@amsterdam.nl"
__status__ = "Dev"

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import Point, box

from gefxml_reader import Cpt, Bore

class Cptverzameling():
    def __init__(self):
        self.cpts = []

    def load_multi_cpt(self, fileList):
        for f in fileList:
            cpt = Cpt()
            cpt.load_xml(f, checkAddFrictionRatio=True, checkAddDepth=True, file=False)
            self.cpts.append(cpt)

class Boreverzameling():
    def __init__(self):
        self.bores = []
    
    def load_multi_bore(self, fileList):
        for f in fileList:
            print(f)
            bore = Bore()
            if f.lower().endswith("xml"):
                bore.load_xml(f)
                self.bores.append(bore)
            elif f.lower().endswith("gef"):
                bore.load_gef(f)
                self.bores.append(bore)

    def load_sikb(self, locationFiles):
        # sikb bestanden zijn zelf al verzamelingen
        # het zijn oorspronkelijk xml, die met de gefxml_viewer omgezet worden in
        # een csv met locaties en een bijbehorende map met boringen in csv
        for locationFile in locationFiles:
            locations = pd.read_csv(locationFile, sep=';')

            # filter alleen de locaties met een boorbeschrijving
            locations = locations[locations['boorbeschrijving']]
            # zet de boringid om in een string om te voorkomen dat 0 aan het begin wordt afgeknipt
            locations['boring'] = locations['boring'].astype(str)
            # elke regel in het bestand met locaties is een boring
            for row in locations.itertuples():
                try:
                    bore = Bore()
                    testid = getattr(row, 'boring')
                    # de boring staat in een mapje met dezelfde naam als het bestand met de locaties
                    boreFile = f'{locationFile.replace(".csv", "")}/{testid}.csv'
                    # lees de boring in
                    bore.from_sikb_csv(testid, boreFile, locationFile)
                    self.bores.append(bore)
                except Exception as e:
                    print(locationFile, row, e)

class GeotechnischLengteProfiel():
    def __init__(self):
        self.line = None
        self.cpts = None
        self.materials = None
        self.boundaries = {}
        self.groundlevelRel = []
        self.groundlevelAbs = []
        self.profilename = ''

    def set_line(self, line):
        self.line = line

    def set_cpts(self, cptVerzameling):
        self.cpts = cptVerzameling.cpts

    def set_bores(self, boreVerzameling):
        self.bores = boreVerzameling.bores

    def set_profilename(self, profilename):
        self.profilename = profilename

    def set_layers(self, materialsTable):
        materials = pd.read_excel(materialsTable, index_col="laag")
        self.materials = materials
     
    def project_on_line(self):
        for cpt in self.cpts:
            cptLocation = Point(cpt.easting, cpt.northing)
            cpt.projectedLocation = self.line.project(cptLocation, normalized=True)
        for bore in self.bores:
            boreLocation = Point(bore.easting, bore.northing)
            bore.projectedLocation = self.line.project(boreLocation, normalized=True)

    def set_groundlevel(self):
        # TODO: dit is niet zo mooi, twee keer hetzelfde
        for bore in self.bores:
            self.groundlevelRel.append([bore.projectedLocation, bore.groundlevel])
            self.groundlevelAbs.append([bore.projectedLocation * self.line.length, bore.groundlevel])
        for cpt in self.cpts:
            self.groundlevelRel.append([cpt.projectedLocation, cpt.groundlevel])
            self.groundlevelAbs.append([cpt.projectedLocation * self.line.length, cpt.groundlevel])

        self.groundlevelAbs.sort()
        self.groundlevelAbs.insert(0, [0, self.groundlevelAbs[0][1]])
        self.groundlevelAbs.append([self.line.length, self.groundlevelAbs[-1][1]])
        self.groundlevelAbs = np.asarray(self.groundlevelAbs)

        self.groundlevelRel.sort()
        self.groundlevelRel.insert(0, [0, self.groundlevelRel[0][1]])
        self.groundlevelRel.append([self.line.length, self.groundlevelRel[-1][1]])
        self.groundlevelRel = np.asarray(self.groundlevelRel)



    def plot(self, boundaries, profilename): #TODO: pas op bij opschonen, de boundaries veranderen nog weleens
        fig = plt.figure()
        ax1 = fig.add_subplot(211)

        # maak een grid
#        plt.grid(b=True) # TODO: dit is uitgezet
        plt.minorticks_on()
#        plt.grid(b=True, which="minor", lw=0.1) # TODO: dit is uitgezet
        
        # plot de cpts
        for cpt in self.cpts:
            qcX = cpt.data["coneResistance"] / 2 + cpt.projectedLocation * self.line.length # TODO: ipv een vaste waarde een factor afhankelijk van aantal cpts en tussenafstand?
            rfX = cpt.data["frictionRatio"] / 2 + cpt.projectedLocation * self.line.length # TODO: ipv vaste waarde een factor afhankelijk van aantal cpts en tussenafstand?
            y = -1 * cpt.data["depth"] + cpt.groundlevel
            plt.plot(qcX, y, c="blue", linewidth=0.5)
            plt.plot(rfX, y, c="green", linewidth=0.5)
            # labels in de figuur kunnen storend zijn, daarom een optie om ze uit te zetten
            # TODO: dit moet ergens anders ingesteld.
            includeLabels = True
            if includeLabels:
                plt.text(qcX.min(), y.max(), cpt.testid, rotation="vertical", fontsize='x-small')

        # plot de boringen
        materials = {0: 'grind', 1: 'zand', 2: 'klei', 3: 'leem', 4: 'veen', 5: 'silt', 6: 'overig'}
        colorsDict = {0: "orange", 1: "yellow", 2: "green", 3: "yellowgreen", 4: "brown", 5: "grey", 6: "black"} # BRO style # TODO: import from gefxml_viewer?

        # voeg een legenda toe
        import matplotlib.patches as mpatches
        handles = []
        for i in materials.keys():
            handles.append(mpatches.Patch(color=colorsDict[i], label=materials[i]))
        ax1.legend(handles=handles, fontsize='xx-small')

        plotAllMaterial = True
        if plotAllMaterial:
            for bore in self.bores:
                boreX = bore.projectedLocation * self.line.length
                for descriptionLocation, soillayers in bore.soillayers.items():
                    if "upper_NAP" in soillayers.columns:
                        uppers = list(soillayers["upper_NAP"])
                        lowers = list(soillayers["lower_NAP"])
                        components = list(soillayers["components"])

                        for upper, lower, component in reversed(list(zip(uppers, lowers, components))):
                            left = 0
                            # TODO: kan dit beter. Gemaakt vanwege een geval met component = nan (lab boring van Anthony Moddermanstraat)
                            if type(component) is dict:
                                for comp, nr in component.items():
                                    barPlot = plt.barh(lower, width=2*comp, left=left+boreX, height=upper-lower, color=colorsDict[nr], align="edge")
                                    left += 2*comp
                        # labels in de figuur kunnen storend zijn, daarom een optie om ze uit te zetten
                        # TODO: dit moet ergens anders ingesteld.
                        includeLabels = True
                        if includeLabels:
                            plt.text(boreX, bore.groundlevel, bore.testid, rotation="vertical", fontsize='x-small')
        else:
            # maak een eenvoudige plot van een boring
            for bore in self.bores:
                boreX = bore.projectedLocation * self.line.length
                for i, layer in bore.soillayers['veld'].iterrows(): # plot alleen de veldbeschrijving, deze is als optie toegevoegd rond 19 mei 2022 aan de gefxml_viewer
                    mainMaterial = layer.components[max(layer.components.keys())]
                    plotColor = colorsDict[mainMaterial]
                    plt.plot([boreX, boreX], [layer.upper_NAP, layer.lower_NAP], plotColor, lw=4, alpha=0.7) # TODO: xml boringen hebben een attribute plotColor, dat is niet meer nodig
                # labels in de figuur kunnen storend zijn, daarom een optie om ze uit te zetten
                # TODO: dit moet ergens anders ingesteld.
                includeLabels = True
                if includeLabels:
                    plt.text(boreX, bore.groundlevel, bore.testid, rotation="vertical", fontsize='x-small')

        # plot maaiveld
        x = [xy[0] for xy in self.groundlevelAbs.tolist()]
        y = [xy[1] for xy in self.groundlevelAbs.tolist()]
        plt.plot(x, y, "k--", lw=0.5)

        # plot de laaggrenzen als lijnen
        for boundary, points in boundaries.items():
            points = np.array(points)
            plt.plot(points[:,0], points[:,1], c="black")

        # kleur de lagen
        for boundary in boundaries.keys():
            if boundary < max(boundaries.keys()):
                pointsTop = np.array(boundaries[boundary + 1])
                pointsBottom = np.array(boundaries[boundary])

                xTop = pointsTop[:,0]
                yTop = pointsTop[:,1]
                xBottom = pointsBottom[:,0]
                yBottom = pointsBottom[:,1]

                # zorgen dat beide lijnen dezelfde x-coördinaten hebben
                allX = np.concatenate((xTop, xBottom))
                allX = np.unique(allX)
                allX = np.sort(allX)
                
                # y waarden interpoleren
                allYTop = np.interp(allX, xTop, yTop)
                allYBottom = np.interp(allX, xBottom, yBottom)            

                plt.fill_between(allX, allYBottom, allYTop, color=self.materials.loc[boundary]["kleur"])

        # optie om alleen de bovenste meters te plotten
        plotTop = False # TODO: dit moet ergens anders als variabele worden doorgegeven
        if plotTop:
            ax1.set_ylim(-5, 2)

        # Tweede as aan de rechterkant van de plot
        ax2 = ax1.twinx().set_ylim(ax1.get_ylim())
        
        # stel de assen in
        ax1.set_xlabel("afstand [m]")
        ax1.set_ylabel("niveau [m t.o.v. NAP]")

        # beperk de plot tot lengte van de profiellijn
        ax1.set_xlim(left=0) # TODO: dit werkt niet handig als je de coördinaten uit grondonderzoek haalt. right=self.line.length

        plt.suptitle(profilename)
        fig.text(0.05, 0.15, 'Ingenieursbureau Gemeente Amsterdam - Team WGM - Vakgroep Geotechniek', fontsize='x-small')

        return fig