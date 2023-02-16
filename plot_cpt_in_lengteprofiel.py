import os

from geotechnisch_lengteprofiel import Cptverzameling, Boreverzameling, GeotechnischLengteProfiel

from gefxml_reader import Cpt, Bore, Test

def readCptBores(path):

    files = os.listdir(path)
    files = [path + f for f in files]
    cptList = []
    boreList = []
    sikbFileList = []

    for f in files:
        if f.lower().endswith('gef'):
            testType = Test().type_from_gef(f)
            if testType == 'cpt':
                cptList.append(f)
            elif testType == 'bore':
                boreList.append(f)
        elif f.lower().endswith('xml'):
            testType = Test().type_from_xml(f)
            if testType == 'cpt':
                cptList.append(f)
            elif testType == 'bore':
                boreList.append(f)
        elif f.lower().endswith('csv'):
            sikbFileList.append(f)

    return boreList, cptList, sikbFileList

def make_multibore_multicpt(boreList, cptList, sikbLocationFileList):
    multicpt = Cptverzameling()
    multicpt.load_multi_cpt(cptList)
    multibore = Boreverzameling()
    multibore.load_multi_bore(boreList)
    multibore.load_sikb(sikbLocationFileList)
    return multicpt, multibore

def plotBoreCptInProfile(multicpt, multibore, line, profileName):
    gtl = GeotechnischLengteProfiel()
    gtl.set_line(line)
    gtl.set_cpts(multicpt)
    gtl.set_bores(multibore)
    gtl.project_on_line()
    gtl.set_groundlevel()
    fig = gtl.plot(boundaries={}, profilename=profileName)
    return fig