import ee
import geemap
import geopandas as gpd
import pandas as pd
import math
from shapely.geometry import Point

# functions --------------------------------------------------
# grilla de un 1km para extraer puntos 
def crear_grilla_regular(gdf, resolucion_m=1000):
    bounds = gdf.total_bounds
    xmin, ymin, xmax, ymax = bounds
    resolucion_grados = resolucion_m / 111320

    puntos = []
    id_counter = 0
    y = ymin
    while y <= ymax:
        x = xmin
        while x <= xmax:
            p = Point(x, y)
            if geometry.contains(p):
                puntos.append({'id': id_counter, 'geometry': p})
                id_counter += 1
            x += resolucion_grados
        y += resolucion_grados

    return gpd.GeoDataFrame(puntos, crs="EPSG:4326")


def get_era5_land_hourly(grilla_ee, fecha):

    if isinstance(fecha, str):
        fecha = ee.Date(fecha)
        
    era5 = ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY") \
        .filterDate(fecha, fecha.advance(1, 'hour')) \
        .select(['temperature_2m', 'u_component_of_wind_10m', 'v_component_of_wind_10m', 'dewpoint_temperature_2m']) \
        .first()

    # sample region
    muestra = era5.sampleRegions(
        collection=grilla_ee,
        scale=1000,  # 1km
        geometries=True
    )

    # save data
    df = geemap.ee_to_df(muestra)
    
    df["date_download"] = fecha.getInfo()['value'] / 1000  # epoch seconds
    df["date_download"] = pd.to_datetime(df["date_download"], unit='s', utc=True)
    
    return df
    


# -------------------------------------------------------------

# iniciar sesion gee
ee.Authenticate()  
ee.Initialize(project='tesis-incendios')

# load poligono -----
incendio = 'santa_ana'
satelite = 'noaa1'

## get fechas
data = gpd.read_file(f'data/procesado/satellite_data/union/{satelite}_{incendio}.geojson')
fechas = data['date_time'].drop_duplicates().reset_index(drop=True)
#fechas2 = data['date_time'].drop_duplicates().reset_index(drop=True)
#fechas = pd.concat([fechas, fechas2], axis =0)

#fechas.drop_duplicates(inplace=True)
# del data

## area
path_area = f"data/procesado/areas/{incendio}.geojson" 

gdf = gpd.read_file(path_area)
gdf = gdf.to_crs("EPSG:4326")
geometry = gdf.union_all()


## creando grillo 1km ----
grilla = crear_grilla_regular(gdf)

## grilla a feature collection gee
features = [
    ee.Feature(ee.Geometry.Point([row.geometry.x, row.geometry.y]), {'id': int(row.id)}) 
    for _, row in grilla.iterrows()
]
grilla_ee = ee.FeatureCollection(features)



# inicio descarga para las fechas ----
lista_gdf = []
for fecha in fechas:
    
    print(fecha)
    fecha_obj = fecha.strftime('%Y-%m-%dT%H:00')
    
    aux = get_era5_land_hourly(grilla_ee=grilla_ee, fecha=fecha_obj)
    aux['date_time'] = fecha
    
    aux_geo = grilla.merge(aux, on = 'id', how = 'left')
    print('valores NA: ', aux_geo.isna().sum())

    lista_gdf.append(aux_geo.dropna())
    

gdf_final = pd.concat(lista_gdf, ignore_index=True)
gdf_final = gpd.GeoDataFrame(gdf_final, geometry='geometry', crs=lista_gdf[0].crs).drop(['id'], axis = 1)

gdf_final.to_file(f'data/procesado/era5/era5_{incendio}_puntos.geojson')
