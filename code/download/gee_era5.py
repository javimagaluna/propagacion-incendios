import ee
import geemap
import geopandas as gpd
import pandas as pd
import numpy as np

from shapely.geometry import box

ee.Authenticate()  
ee.Initialize(project='tesis-incendios')

################################################################################

def process_era5_cells(fecha_objetivo, fc, variables=None):
    """
    Descarga datos de ERA5-Land Hourly desde GEE, reducidos sobre la grilla HealPix.

    Parameters
    ----------
    fecha_objetivo : str or ee.Date
        Fecha en formato 'YYYY-MM-DD HH:MM' UTC para consultar ERA5.
    fc : ee.FeatureCollection
        Grilla HealPix de interés (FeatureCollection).
    variables : list or None
        Lista de variables a extraer (bandas). Si None, usa variables por defecto.

    Returns
    -------
    df : GeoDataFrame
        DataFrame con valores promedio de ERA5-Land en cada celda HealPix.
    """
    if isinstance(fecha_objetivo, str):
        fecha_objetivo = ee.Date(fecha_objetivo)

    if variables is None:
        variables = [
            'u_component_of_wind_10m',
            'v_component_of_wind_10m',
            'temperature_2m',
            'dewpoint_temperature_2m'
        ]

    era5 = ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY") \
                .filterDate(fecha_objetivo, fecha_objetivo.advance(1, 'hour')) \
                .select(variables) \
                .first()

    scale_reprojection = 9000 

    # reducir a la grilla (no healphix porque produce NAs)
    fc_reduced = era5.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale_reprojection
    )
 
    # to GeoDataFrame
    df = geemap.ee_to_df(fc_reduced)
    
    # add fecha
    df["date_time"] = fecha_objetivo.getInfo()['value'] / 1000  # epoch seconds
    df["date_time"] = pd.to_datetime(df["date_time"], unit='s', utc=True)

    return df


def intersect_ponderado_area(gdf_fecha, area_filtrado, variables = ['dewpoint_temperature_2m',
                                                                    'temperature_2m',
                                                                    'u_component_of_wind_10m',
                                                                    'v_component_of_wind_10m'
                                                                    ]
                             ):
    """
    Realiza la intersección ponderada por área de los valores de ERA5
    sobre las celdas HealPix de área_filtrado.
    
    Parameters:
    ----------
    gdf_fecha : GeoDataFrame
        GeoDataFrame con polígonos de ERA5 y valores climáticos.
    area_filtrado : GeoDataFrame
        GeoDataFrame con la grilla HealPix de áreas pequeñas.
    variables : list of str
        Lista de nombres de columnas con variables climáticas a ponderar.
    
    Returns:
    --------
    GeoDataFrame
        area_filtrado con columnas de variables ponderadas.
    """
    crs_proj = area_filtrado.estimate_utm_crs()
    gdf_fecha_proj = gdf_fecha.to_crs(crs_proj)
    area_filtrado_proj = area_filtrado.to_crs(crs_proj)

    inter = gpd.overlay(area_filtrado_proj, gdf_fecha_proj, how='intersection')
    inter['area_inter'] = inter.geometry.area

    area_filtrado_proj['area_celda'] = area_filtrado_proj.geometry.area
    
    if "area_celda" in inter.columns:
        inter = inter.drop(columns=["area_celda"])
    
    inter = inter.merge(area_filtrado_proj[['Codigo', 'area_celda']], on='Codigo', how='left')

    ## ponderar por interseccion area
    inter['peso'] = inter['area_inter'] / inter['area_celda']
    
    for var in variables:
        inter[f'{var}_pond'] = inter[var] * inter['peso']

    agregados = (
        inter.groupby('Codigo')[[f'{var}_pond' for var in variables]]
        .sum()
        .reset_index()
    )

    # promedio ponderado
    suma_pesos = (
        inter.groupby('Codigo')['peso']
        .sum()
        .reset_index()
        .rename(columns={'peso': 'peso_total'})
    )
    agregados = agregados.merge(suma_pesos, on='Codigo', how='left')
    
    for var in variables:
        agregados[f'{var}_ponderado'] = agregados[f'{var}_pond'] / agregados['peso_total']

    resultado = area_filtrado.merge(
        agregados[['Codigo'] + [f'{var}_ponderado' for var in variables]],
        on='Codigo',
        how='left'
    )

    return resultado



#######################################################

fecha_noaa1 = gpd.read_file('data/procesado/satellite_data/union/zonas_noaa1.geojson')[['zona', 'date_time']].drop_duplicates()
fecha_noaa2 = gpd.read_file('data/procesado/satellite_data/union/zonas_noaa2.geojson')[['zona', 'date_time']].drop_duplicates()
fecha_suomi = gpd.read_file('data/procesado/satellite_data/union/zonas_suomi.geojson')[['zona', 'date_time']].drop_duplicates()

fechas_gen = pd.concat([fecha_noaa1, fecha_noaa2, fecha_suomi]).reset_index(drop = True)
fechas_gen['fecha_gee'] = fechas_gen.date_time.dt.strftime('%Y-%m-%dT%H:00')

areas = gpd.read_file("data/procesado/grilla/areas_grilla_healpix.geojson")

zonas =  areas['zona'].unique()
path_save = 'data/procesado/era5'

for zona in zonas:
    print(zona + '--------------------')
    
    fechas = fechas_gen[fechas_gen['zona']== zona]['fecha_gee'].unique()
    gdf_zona = areas[areas['zona'] ==zona]
    
    ## transformamos area y generamos recuadros mas grandes pues genera valores validos (no hay NAs)
    gdf_zona_utm = gdf_zona.to_crs(gdf_zona.estimate_utm_crs())
    minx, miny, maxx, maxy = gdf_zona_utm.total_bounds

    grid_polygons = []
    grid_size = 1035 #1090 #1100 

    x_left = minx
    while x_left < maxx:
        y_bottom = miny
        while y_bottom < maxy:
            x_right = x_left + grid_size
            y_top = y_bottom + grid_size
            grid_polygons.append(box(x_left, y_bottom, x_right, y_top))
            y_bottom += grid_size
        x_left += grid_size

    grid_gdf = gpd.GeoDataFrame({"geometry": grid_polygons}, crs=gdf_zona_utm.crs)
    grid_gdf['id'] = range(0, grid_gdf.shape[0])   # id para mapear posteriormente las coords
    
    ## to fc
    fc = geemap.geopandas_to_ee(grid_gdf)

    lista_gdf = []
    for fecha in fechas:
        print(fecha)
        df = process_era5_cells(fecha, fc)
        df = grid_gdf.merge(df, on = 'id', how = 'left')
        
        print(df.isna().sum())
        
        lista_gdf.append(df)

    gdf_final = pd.concat(lista_gdf, ignore_index=True)
    gdf_final = gpd.GeoDataFrame(gdf_final, geometry='geometry', crs=lista_gdf[0].crs).drop(['id'], axis = 1)
    
    gdf_final.to_file(path_save+f'/info_era5_{zona}_grilla.geojson')



for zona in zonas:
    
    print(zona +'---------------------')
    gdf = gpd.read_file(path_save+f'/info_era5_{zona}_grilla.geojson')
    area_filtrado = areas[areas['zona'] == zona]
    
    fechas = gdf['date_time'].unique()
    
    lista_gdf = []
    for fecha in fechas:
        print(fecha)
        gdf_fecha = gdf[gdf['date_time'] == fecha]
        
        gdf_inter = intersect_ponderado_area(gdf_fecha, area_filtrado)

        gdf_inter['date_time'] = fecha
        
        ## velocidad del viento
        gdf_inter['wind_speed_10m'] = (gdf_inter['u_component_of_wind_10m_ponderado']**2 + gdf_inter['v_component_of_wind_10m_ponderado']**2) ** 0.5
        ## direccion del viento
        gdf_inter['wind_dir_10m'] = (np.degrees(np.arctan2(-gdf_inter['u_component_of_wind_10m_ponderado'],-gdf_inter['v_component_of_wind_10m_ponderado'])) + 360) % 360

        ## humedad relativa:
        es_Td = 6.112 * np.exp((17.67 * (gdf_inter['dewpoint_temperature_2m_ponderado'] - 273.15)) / (gdf_inter['dewpoint_temperature_2m_ponderado'] - 29.65))
        es_T = 6.112 * np.exp((17.67 * (gdf_inter['temperature_2m_ponderado'] - 273.15)) / (gdf_inter['temperature_2m_ponderado'] - 29.65))

        gdf_inter['relative_humidity'] = 100 * es_Td / es_T
        
        ## Deficit de presion de vapor
        gdf_inter['VPD'] = es_T - es_Td
        
        ## transformacion a grados
        gdf_inter['temperature_2m_C'] = gdf_inter['temperature_2m_ponderado'] - 273.15
        gdf_inter['dewpoint_temperature_2m_ponderado'] = gdf_inter['dewpoint_temperature_2m_ponderado'] - 273.15
        
        lista_gdf.append(gdf_inter)


    gdf_final = pd.concat(lista_gdf, ignore_index=True)
    gdf_final = gpd.GeoDataFrame(gdf_final, geometry='geometry', crs=lista_gdf[0].crs)
    
    gdf_final.to_file(path_save+f'/era5_{zona}_healpix.geojson')



gdf_resultado = gdf_final.to_crs("EPSG:4326")

##########################################
## plot

aux = gdf_final[gdf_final.date_time == '2025-04-18 08:00:00+00:00']
gdf_filt = gdf[gdf.date_time == '2025-04-18 08:00:00+00:00']

import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8,8))
gdf_filt.plot(column="dewpoint_temperature_2m", cmap="viridis", legend=True, ax=ax)
plt.title("Pendiente por celda")
plt.show()


fig, ax = plt.subplots(figsize=(8,8))
aux.plot(column="dewpoint_temperature_2m_ponderado", cmap="viridis", legend=True, ax=ax)
plt.title("Pendiente por celda")
plt.show()






##########################################
############## conexion api ##############
### no usado

# import cdsapi

# dataset = "reanalysis-era5-land"
# request = {
#     "variable": [
#         "2m_dewpoint_temperature",
#         "2m_temperature",
#         "10m_u_component_of_wind",
#         "10m_v_component_of_wind",
#         "surface_pressure"
#     ],
#     "year": "2025",
#     "month": "04",
#     "day": [
#         "12", "13", "14",
#         "15", "16", "17",
#         "18", "19", "20",
#         "21", "22"
#     ],
#     "time": [
#         "06:00", "07:00", "08:00",
#         "18:00", "19:00", "20:00"
#     ],
#     "data_format": "netcdf",
#     "download_format": "zip",
#     "area": [35.97, -94.81, 35.91, -94.75]
# }

# client = cdsapi.Client()
# client.retrieve(dataset, request).download()

