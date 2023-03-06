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
                    dl.WMSTileLayer(url='https://service.pdok.nl/bzk/brocptkenset/wms/v1_0', layers='cpt_kenset', opacity=0.5),
                    dl.WMSTileLayer(url='https://service.pdok.nl/bzk/bro-geotechnischbooronderzoek/wms/v1_0', layers='bhrgt_kenset', opacity=0.5)
                ])

# Create layout.
dash_app.layout = html.Div([
    dcc.Store(id='points', storage_type='memory', data=[]), # TODO: kunnen we die store vermijden? Het zou beter zijn om een willekeurig aantal punten te klikken en dan een knop?
    html.H1("Klik op de kaart om een profiellijn te maken"),
    mapGraph,
    html.Button('maak profiel', id='create-profile'),    
    dcc.Store(id='download-store', storage_type='memory'), # tijdelijke opslag van afbeeldingen voor download
    html.Button('download PNG', id='downloadPngButton'),
    dcc.Download(id='downloadPng'),
    html.Button('download PDF', id='downloadPdfButton'),
    dcc.Download(id='downloadPdf'),
    html.Img(id='profile', style={'width': '1000px'})
])


@dash_app.callback(
    Output("layer", "children"),
    Output("points", "data"),
    Input("map-id", 'click_lat_lng'),
    Input("layer", "children"),
    Input("points", "data")
    )
def points_on_map(e, children, points):
    if e is not None:
        children.append(dl.Marker(position=e))
        points.append([e[1],e[0]])

    return children, points

@dash_app.callback(
    Output('profile', 'src'), # de afbeelding die je direct ziet
    Output("download-store", "data"), # de afbeelding voor download
    Input("create-profile", 'n_clicks'),
    State("points", "data"),
    prevent_initial_call=True
    )
def make_profile(click, points):
    line = LineString(points)
    objectDF = pd.DataFrame().from_dict({"KUNSTWERKN": ['lijn'], "geometry": [line]})
    objectGDF = gpd.GeoDataFrame(objectDF).set_crs('epsg:4326').to_crs('epsg:28992')

    objecten = objectGDF["KUNSTWERKN"]
    buffer = 50

    for obj in objecten:
        objectData = objectGDF[objectGDF["KUNSTWERKN"] == obj]
        objectBuffer = objectData.buffer(buffer).unary_union

        cptList = haal_BRO(obj, objectBuffer, tests=[], geometries=[], gefType='GEF-CPT')
        boreList = haal_BRO(obj, objectBuffer, tests=[], geometries=[], gefType='GEF-BORE')
        multicpt, multibore = make_multibore_multicpt(boreList=boreList, cptList=cptList, sikbLocationFileList=[])

    fig = plotBoreCptInProfile(multicpt, multibore, objectData.loc[0, 'geometry'], profileName="")

    # https://stackoverflow.com/questions/49851280/showing-a-simple-matplotlib-plot-in-plotly-dash
    buf = io.BytesIO()
    fig.savefig(buf, format = "png") # TODO: maak hiervan een svg
    dataPng = base64.b64encode(buf.getbuffer()).decode("utf-8") # encode to html elements
    
    fig.savefig(buf, format = "pdf") # TODO: maak hiervan een svg
    dataPdf = base64.b64encode(buf.getbuffer()).decode("utf-8") # encode to html elements

    return f"data:image/png;base64,{dataPng}", {'png': dataPng, 'pdf': dataPdf}


@dash_app.callback(
    Output('downloadPng', 'data'),
    Input('downloadPngButton', 'n_clicks'),
    State('download-store', 'data'),
    prevent_initial_call=True
)
def func(n_clicks, data):
    print(n_clicks)
    return {'base64': True, 'content': data['png'], 'filename': 'profiel.png', 'type': 'image/png'}


@dash_app.callback(
    Output('downloadPdf', 'data'),
    Input('downloadPdfButton', 'n_clicks'),
    State('download-store', 'data'),
    prevent_initial_call=True
)
def func(n_clicks, data):
    print(n_clicks)
    return {'base64': True, 'content': data['pdf'], 'filename': 'profiel.pdf', 'type': 'object/pdf'}

if __name__ == '__main__':
    app.run(debug=True)