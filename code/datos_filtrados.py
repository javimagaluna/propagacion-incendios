from pathlib import Path
import geopandas as gpd
import pandas as pd

from shapely.geometry import Polygon, Point, box
import re
from datetime import datetime, timedelta

import matplotlib.pyplot as plt

carpeta = "data/procesado/satellite_data/suomi"
archivos = [f.name for f in Path(carpeta).iterdir() if f.is_file()]
regex = re.compile(r"A\d{7}\.\d{4}\.\d{3}") 


def extraer_fecha(cadena):
    año = int(cadena[1:5])
    dia_juliano = int(cadena[5:8])
    hora = int(cadena[9:11])
    minuto = int(cadena[11:13])
    
    fecha = datetime(año, 1, 1) + timedelta(days=dia_juliano - 1)
    fecha = fecha.replace(hour=hora, minute=minuto)
    return fecha

def make_pixel_square(point, size=375):
    half = size / 2
    return box(point.x - half, point.y - half, point.x + half, point.y + half)



gdf_zonas = []
for id in range(len(archivos)):
    
    arch = archivos[id]
    print(arch)
    fecha = regex.search(str(arch)).group()
    data = gpd.read_file(carpeta + '/' + arch)
    data['date_time'] = extraer_fecha(fecha)
    data['date_file'] = fecha
    
    gdf_zonas.append(data)

gdf_zonas = gpd.GeoDataFrame(pd.concat(gdf_zonas, ignore_index=True), crs=gdf_zonas[0].crs) 


gdf_zonas2 = gdf_zonas[gdf_zonas['I02_uncert_index'].isna()]

aux = gdf_zonas2[gdf_zonas2.eval('zona == "bee_rock_creek"')]

momento1 = aux[aux['date_time'] == '2025-04-15 07:24:00']
momento2 =  aux[aux['date_time'] == '2025-04-16 07:06:00']



gdf_m = momento1.to_crs("EPSG:5070") 
gdf_m2 = momento2.to_crs("EPSG:5070") 

gdf_m['geometry'] = gdf_m.geometry.apply(lambda p: make_pixel_square(p, size=375))
gdf_m2['geometry'] = gdf_m2.geometry.apply(lambda p: make_pixel_square(p, size=375))

gdf_pixel_polys1 = gdf_m.to_crs("EPSG:4326")
gdf_pixel_polys2 = gdf_m2.to_crs("EPSG:4326")

