from dash import Dash, dcc, html, Input, Output, State
import pandas as pd
import geopandas as gpd
import dash_leaflet as dl
from shapely.geometry import LineString
import io
import base64

from plot_cpt_in_lengteprofiel import make_multibore_multicpt, plotBoreCptInProfile
from omnoemen_pdf import haal_BRO

external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css']
dash_app = Dash(__name__, external_stylesheets=external_stylesheets)
app = dash_app.server

markers = []
mapGraph = dl.Map(
                id="map-id", 
                style={'width': '1000px', 'height': '500px'}, 
                center=[52.4, 4.9], zoom=12, 
                children=[
                    dl.TileLayer(),
                    dl.LayerGroup([], id="layer"),
                    dl.WMSTileLayer(url='https://service.pdok.nl/bzk/brocptkenset/wms/v1_0', layers='cpt_kenset', opacity=0.5)
                ])

# Create layout.
dash_app.layout = html.Div([
    dcc.Store(id='points', storage_type='memory', data=[]),
    html.H1("Klik twee keer om een profiel te maken"),
    mapGraph,
    html.Img(id='profile', style={'width': '1000px'})
])


@dash_app.callback(
    Output("layer", "children"),
    Output('profile', 'src'),
    Output("points", "data"),
    Input("map-id", 'click_lat_lng'),
    State("points", "data"),
    State("layer", "children")
    )
def click_coord(e, points, children):
    if e is not None:
        points.append([e[1],e[0]])
        children.append(dl.Marker(position=e))

    if len(points) == 2:
        line = LineString(points)
        objectDF = pd.DataFrame().from_dict({"KUNSTWERKN": ['lijn'], "geometry": [line]})
        objectGDF = gpd.GeoDataFrame(objectDF).set_crs('epsg:4326').to_crs('epsg:28992')

        objecten = objectGDF["KUNSTWERKN"]
        buffer = 50

        for obj in objecten:
            objectData = objectGDF[objectGDF["KUNSTWERKN"] == obj]
            objectBuffer = objectData.buffer(buffer).unary_union

            cptList = haal_BRO(obj, objectBuffer, tests=[], geometries=[], gefType='GEF-CPT')
            multicpt, multibore = make_multibore_multicpt(boreList=[], cptList=cptList, sikbLocationFileList=[])

            fig = plotBoreCptInProfile(multicpt, multibore, objectData.loc[0, 'geometry'], profileName="")

            # https://stackoverflow.com/questions/49851280/showing-a-simple-matplotlib-plot-in-plotly-dash
            buf = io.BytesIO()
            fig.savefig(buf, format = "png") # TODO: maak hiervan een svg
            data = base64.b64encode(buf.getbuffer()).decode("utf8") # encode to html elements
            buf.close()
        
        # TODO: de server onthoudt welke punten er geklikt zijn en dan kun je niks meer.
        # TODO: hoe kun je die punten vergeten?
        # TODO: het zit niet in cookies, want als je op ander apparaat opent, dan staan de punten ook daarin
        return children, f"data:image/png;base64,{data}", []

    return children, '', points

if __name__ == '__main__':
    app.run(debug=True)