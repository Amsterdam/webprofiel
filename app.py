import json
import dash
import pandas as pd
import geopandas as gpd
import plotly.express as px
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input
import dash_leaflet as dl
from shapely.geometry import LineString
import io
import base64
import matplotlib.pyplot as plt

from plot_cpt_in_lengteprofiel import readCptBores, make_multibore_multicpt, plotBoreCptInProfile
from omnoemen_pdf import haal_BRO

app = dash.Dash(__name__, external_scripts=['https://codepen.io/chriddyp/pen/bWLwgP.css'])

markers = []
mapGraph = dl.Map(
                id="map-id", 
                style={'width': '1000px', 'height': '500px'}, 
                center=[52.4, 4.9], zoom=12, 
                children=[
                    dl.TileLayer(),
                    dl.LayerGroup(id="layer")
                ])

# Create layout.
app.layout = html.Div([
    html.H1("Klik twee keer om een profiel te maken"),
    mapGraph,
    html.P("Coordinate (click on map):"),
    html.Img(id='profile', style={'width': '1000px'})
])

points = []
tests =[]
geometries = []

@app.callback(
    Output("layer", "children"),
    Output('profile', 'src'),
    Input("map-id", 'click_lat_lng')
    )
def click_coord(e):
    if e is not None:
        points.append([e[1],e[0]])
        mapGraph.children.append(dl.Marker(position=e))
    else:
        pass

    if len(points) == 2:
        line = LineString(points)
        objectDF = pd.DataFrame().from_dict({"KUNSTWERKN": ['lijn'], "geometry": [line]})
        objectGDF = gpd.GeoDataFrame(objectDF).set_crs('epsg:4326').to_crs('epsg:28992')

        objecten = objectGDF["KUNSTWERKN"]
        buffer = 50

        for obj in objecten:
            objectData = objectGDF[objectGDF["KUNSTWERKN"] == obj]
            objectBuffer = objectData.buffer(buffer).unary_union

            cptList = haal_BRO(obj, objectBuffer, tests, geometries, 'GEF-CPT')

            boreList = []
            sikbFileList = []

            multicpt, multibore = make_multibore_multicpt(boreList, cptList, sikbFileList)

            fig = plotBoreCptInProfile(multicpt, multibore, objectData.loc[0, 'geometry'], profileName="")

            # https://stackoverflow.com/questions/49851280/showing-a-simple-matplotlib-plot-in-plotly-dash
            buf = io.BytesIO()
            fig.savefig(buf, format = "png") # TODO: maak hiervan een svg
            data = base64.b64encode(buf.getbuffer()).decode("utf8") # encode to html elements
            buf.close()
            
        return mapGraph.children, "data:image/png;base64,{}".format(data)

    return mapGraph.children, ''

if __name__ == '__main__':
    app.run_server(debug=True)