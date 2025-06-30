import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import re

from datetime import datetime, timedelta

from shapely.geometry import Polygon, Point, box
from shapely.affinity import rotate, translate
import pyproj

import imageio

#########################################################
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


def make_viirs_pixel(lat, lon, zenith_deg, azimuth_deg, size_nadir=375):
    """Crea pixel deformado segun angulo de observacion"""
    zenith_rad = np.deg2rad(zenith_deg)
    width = size_nadir / np.cos(zenith_rad)
    height = size_nadir

    # cuadrado centrado en (0,0)
    hw, hh = width / 2, height / 2
    rect = Polygon([(-hw, -hh), (-hw, hh), (hw, hh), (hw, -hh)])

    # rotar por azimuth
    pixel_rot = rotate(rect, -azimuth_deg, origin=(0, 0), use_radians=False)

    # proyectar punto a metros
    proj = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x0, y0 = proj.transform(lon, lat)

    # trasladar al centroide
    pixel_proj = translate(pixel_rot, xoff=x0, yoff=y0)

    # a lat/lon
    back_proj = pyproj.Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
    return Polygon([back_proj.transform(x, y) for x, y in pixel_proj.exterior.coords])



#########################################################
path_areas = Path('data/procesado/zonas_incendios/areas_buffer.geojson')
areas = gpd.read_file(path_areas)
satelite =  'noaa2'
path_save = 'data/procesado/satellite_data/union'

carpeta = f"data/procesado/satellite_data/{satelite}"
archivos = [f.name for f in Path(carpeta).iterdir() if f.is_file()]
regex = re.compile(r"A\d{7}\.\d{4}\.\d{3}") 


## load data suomi
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
gdf_zonas.to_file(f'{path_save}/zonas_{satelite}.geojson')


### filtrando zona
aux = gdf_zonas[gdf_zonas.eval('zona == "area2"')]
aux.date_time.value_counts()

### filtrando por calidad
aux = aux[aux['I04_quality_flags'].isin([0, 4, 8])]
aux.date_time.value_counts()

### creando buffer
gdf_m = aux.to_crs("EPSG:5070") 
gdf_m['geometry'] = gdf_m.apply(lambda row: make_viirs_pixel(row['latitude'],
                                                             row['longitude'],
                                                             row['sensor_zenith'],
                                                             row['sensor_azimuth']
                                                             ),
                                axis=1)

gdf_pixel_polys = gpd.GeoDataFrame(gdf_m, geometry='geometry', crs='EPSG:4326')

## load healpix

grilla = gpd.read_file('data/procesado/grilla/areas_grilla_healpix.geojson')


# Crear carpeta temporal
os.makedirs("frames", exist_ok=True)

# Escalar los valores una sola vez
vmin = gdf_pixel_polys['I04'].min()
vmax = gdf_pixel_polys['I04'].max()
norm = Normalize(vmin=vmin, vmax=vmax)

grilla_filt = grilla[grilla.eval('zona == "area2"')]

tiempo = gdf_pixel_polys.date_time.unique()
for fecha in tiempo:
    print(fecha)
    gdf =  gdf_pixel_polys[gdf_pixel_polys['date_time'] == fecha]
    
    fig, ax = plt.subplots(figsize=(8, 6))
    grilla_filt.plot(ax=ax, facecolor='none', edgecolor='gray', linewidth=0.5)
    gdf.plot(ax=ax, column="I04", cmap='viridis', edgecolor='black', alpha=0.4, norm=norm)
    
    ax.set_title(f"Incendios - {str(gdf['date_time'].iloc[0])}")
    ax.set_aspect("equal")
    ax.axis('off')
    
    # Colorbar
    sm = plt.cm.ScalarMappable(cmap='viridis', norm=norm)
    sm._A = []
    cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', fraction=0.046, pad=0.04)
    cbar.set_label("I04")
    
    # Guardar frame
    frame_path = f"frames/frame_{gdf.date_file.iloc[0]}.png"
    plt.savefig(frame_path, bbox_inches='tight', dpi=150)
    plt.close()
