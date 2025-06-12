from pathlib import Path
import re
import os

import rioxarray
import geopandas as gpd
import pandas as pd


import warnings
from rasterio.errors import NotGeoreferencedWarning

# Ignorar solo NotGeoreferencedWarning
warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


### load areas
path_areas = Path('data/procesado/zonas_incendios/areas_buffer.geojson')
areas = gpd.read_file(path_areas)


###  identificar pares .nc
regex = re.compile(r"A\d{7}\.\d{4}\.\d{3}")  ## expresion regular para mapear los archivos

path_bandas = Path(r'datos-viirs\NOAA\BANDAS')#Path(r'data\EEUU\capa_viirs_6m_cuadrado')
path_coords = Path(r'datos-viirs\NOAA\COORDS') #Path(r'data\EEUU\VNP03IMG_NRT')

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
        gdf_filtrada = gdf[gdf.geometry.intersects(geom)].copy()
        gdf_filtrada["zona"] = zona 
        gdfs_con_zona.append(gdf_filtrada)

    # Unir todo en un solo GeoDataFrame
    if gdfs_con_zona:
        gdf_unido = gpd.GeoDataFrame(pd.concat(gdfs_con_zona, ignore_index=True), crs=gdf.crs)
        return gdf_unido
    else:
        return gpd.GeoDataFrame(columns=gdf.columns.tolist() + ["zona"], crs=gdf.crs)

## --------------------------------


path_save = 'data/procesado/satellite_data/noaa'

for bandas, coordenadas in pares:
    nombre_archivo = regex.search(str(bandas)).group()
    print('-----------')
    print(nombre_archivo)
    
    if os.path.exists(f'{path_save}/merge_{nombre_archivo}.geojson'):
        print(f"🟡 Archivo ya existe: {nombre_archivo}")
        continue
            
    coords = rioxarray.open_rasterio(coordenadas)
    data_nasa = rioxarray.open_rasterio(bandas)
    
    lat_lon = coords[0][['latitude', 'longitude']].isel(band=0).to_dataframe().reset_index()
    data_bandas = data_nasa.isel(band=0).to_dataframe().reset_index()
    
    data_bandas['I04_scale'] = (data_bandas['I04'] * data_nasa.I04.attrs['scale_factor'] )+ data_nasa.I04.attrs['add_offset']
    data_bandas['I05_scale'] = (data_bandas['I05'] * data_nasa.I05.attrs['scale_factor'] )+ data_nasa.I05.attrs['add_offset']

    print('merge data')
    data_lat_lon = lat_lon.merge(data_bandas, on = ['y', 'x', 'band', 'spatial_ref'], how = 'inner')
    
    data_lat_lon = data_lat_lon.drop(columns = ['band', 'spatial_ref', 'I04_uncert_index', 'I05_uncert_index'],
                                 axis= 1)
    
    print('to geopandas')
    gdf = gpd.GeoDataFrame(data_lat_lon, geometry=gpd.points_from_xy(data_lat_lon.longitude,
                                                                     data_lat_lon.latitude), crs="EPSG:4326")
    
    gdf_unido = filtrar_por_areas_y_unir(gdf, areas)
    print(gdf_unido.zona.value_counts()) 
    del gdf
    
    print('save file')
    gdf_unido.to_file(f'{path_save}/merge_{nombre_archivo}.geojson')












