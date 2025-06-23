from pathlib import Path
import re
import os

import rioxarray
import xarray as xr
import geopandas as gpd
import pandas as pd


import warnings
from rasterio.errors import NotGeoreferencedWarning

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)

## --------------------------------

### load areas
path_areas = Path('data/procesado/zonas_incendios/areas_buffer.geojson')
areas = gpd.read_file(path_areas)


###  identificar pares .nc
regex = re.compile(r"A\d{7}\.\d{4}\.\d{3}")  ## expresion regular para mapear los archivos

path_bandas = Path(r'datos-viirs\SUOMI\BANDAS')
path_coords = Path(r'datos-viirs\SUOMI\COORDS') 

archivos_bandas = {regex.search(f.name).group(): f for f in path_bandas.glob("*.nc") if regex.search(f.name)}
archivos_coords = {regex.search(f.name).group(): f for f in path_coords.glob("*.nc") if regex.search(f.name)}

claves_comunes = archivos_bandas.keys() & archivos_coords.keys()

pares = [(archivos_bandas[clave], archivos_coords[clave]) for clave in sorted(claves_comunes)]

# ### archivos que faltan por descargar:
# claves1 = set(archivos_bandas)
# claves2 = set(archivos_coords)
# claves_comunes = claves1 & claves2
# sin_par_en_1 = claves1 - claves2
# sin_par_en_2 = claves2 - claves1

# df_sin_par_1 = pd.DataFrame([
#     {"clave": clave, "archivo_sin_par_carpeta1": str(archivos_bandas[clave])}
#     for clave in sorted(sin_par_en_1)
# ])

# df_sin_par_2 = pd.DataFrame([
#     {"clave": clave, "archivo_sin_par_carpeta2": str(archivos_coords[clave])}
#     for clave in sorted(sin_par_en_2)
# ])

# df_pares = pd.DataFrame([
#     {"clave": clave, "archivo_carpeta1": str(archivos_bandas[clave]), "archivo_carpeta2": str(archivos_coords[clave])}
#     for clave in sorted(claves_comunes)
# ])



## functions ----------------------
def filtrar_por_areas_y_unir(gdf, areas):
    gdfs_con_zona = []

    for id in range(len(areas)):
        zona = areas['zona'].iloc[id]
        geom = areas['geometry'].iloc[id]
        gdf_filtrada = gdf[gdf.geometry.intersects(geom)].copy()   ## nos quedamos con los centroides que intersecten en algun lugar del poligono
        gdf_filtrada["zona"] = zona 
        gdfs_con_zona.append(gdf_filtrada)

    # Unir todo en un solo GeoDataFrame
    if gdfs_con_zona:
        gdf_unido = gpd.GeoDataFrame(pd.concat(gdfs_con_zona, ignore_index=True), crs=gdf.crs)
        return gdf_unido
    else:
        return gpd.GeoDataFrame(columns=gdf.columns.tolist() + ["zona"], crs=gdf.crs)

## --------------------------------


path_save = 'data/procesado/satellite_data/suomi'

for bandas, coordenadas in pares:
    nombre_archivo = regex.search(str(bandas)).group()
    print('-----------')
    print(nombre_archivo)
    
    if os.path.exists(f'{path_save}/merge_{nombre_archivo}.geojson'):
        print(f"Archivo ya existe: {nombre_archivo}")
        continue
            
    coords = rioxarray.open_rasterio(coordenadas)
    data_nasa = rioxarray.open_rasterio(bandas)
    data_nasa.data_vars
    data_nasa.attrs
    
    # VNP03IMG coordenadas y angulos
    lat = coords[0]['latitude'].isel(band=0)
    lon = coords[0]['longitude'].isel(band=0)
    sensor_zenith = (coords[0]['sensor_zenith'].isel(band=0) * coords[0].sensor_zenith.attrs['scale_factor'] )+ coords[0].sensor_zenith.attrs['add_offset']
    sensor_azimuth = (coords[0]['sensor_azimuth'].isel(band=0) * coords[0].sensor_azimuth.attrs['scale_factor'] )+ coords[0].sensor_azimuth.attrs['add_offset']
    
    # VNP02IMG bandas termicas escaladas
    i04_scaled = (data_nasa['I04'].isel(band=0) * data_nasa.I04.attrs['scale_factor'] )+ data_nasa.I04.attrs['add_offset']
    i05_scaled = (data_nasa['I05'].isel(band=0) * data_nasa.I05.attrs['scale_factor'] )+ data_nasa.I05.attrs['add_offset']
    
    ## incertidumbre -> nos sirve para evaluar la precision del valor
    I04_uncert_index = 1 + data_nasa.I04_uncert_index.attrs['scale_factor'] * (data_nasa['I04_uncert_index'].isel(band=0) ** 2)
    I05_uncert_index = 1 + data_nasa.I05_uncert_index.attrs['scale_factor'] * (data_nasa['I05_uncert_index'].isel(band=0) ** 2)
    
    print('creando df')
    
    ds = xr.Dataset({
        'latitude': lat,
        'longitude': lon,
        'sensor_zenith': sensor_zenith,
        'sensor_azimuth': sensor_azimuth,
        'I04': i04_scaled,
        'I05': i05_scaled,  
        'I04_quality_flags':data_nasa['I04_quality_flags'].isel(band=0), 
        'I05_quality_flags': data_nasa['I05_quality_flags'].isel(band=0), 
        'quality_flag': coords[0]['quality_flag'].isel(band=0),
        'I04_uncert_index': I04_uncert_index,
        'I05_uncert_index': I05_uncert_index
    })
    
    df = ds.to_dataframe().reset_index()
    df = df.dropna(subset=['latitude', 'longitude', 'I04', 'I05']) 
    df = df.drop(['x','y', 'band', 'spatial_ref'], axis= 1)
    
    print('to geopandas')
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude,
                                                           df.latitude), crs="EPSG:4326")
    
    gdf_unido = filtrar_por_areas_y_unir(gdf, areas)
    del gdf
    
    if gdf_unido.shape[0]==0:
        print('no hay datos dentro de las zonas')
        continue
    
    print(gdf_unido.zona.value_counts()) 
    
    print('save file')
    gdf_unido.to_file(f'{path_save}/merge_{nombre_archivo}.geojson')



