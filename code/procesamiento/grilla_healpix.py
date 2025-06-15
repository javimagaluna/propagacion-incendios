from rhealpixdggs.dggs import *
import geopandas as gpd
from shapely.geometry import Polygon
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

## areas de incendios (4)
path_areas = Path('data/procesado/zonas_incendios/areas_buffer.geojson')
areas = gpd.read_file(path_areas)

rdggs = RHEALPixDGGS()

Nivel = 10
list_gdf = []

for zona in areas['zona']:
    print(zona)
    coords = areas[areas['zona'] == zona].iloc[0].geometry
    nw = (coords.bounds[0], coords.bounds[3])
    se = (coords.bounds[2], coords.bounds[1])


    polygons = []
    codigo = []
    cells = rdggs.cells_from_region(Nivel, nw, se, plane=False)
    for row in cells:
        for cell in row:
            coordenadas = []
            celda = str(cell)
            primero = [celda[0]]+ [int(c) for c in celda[1:]]
            c = rdggs.cell(primero)
            for d in c.boundary(n=2, plane=False):
                # coord = tuple(my_round(val, 14) for val in d)
                coord = tuple(round(val, 14) for val in d)            
                coordenadas.append(coord)
            if coordenadas[0] != coordenadas[-1]:
                coordenadas.append(coordenadas[0])
            codigo.append(celda)
            polygon = Polygon(coordenadas)
            polygons.append(polygon)

    gdf_healpix = gpd.GeoDataFrame(crs="EPSG:4326", geometry=polygons)
    gdf_healpix['Codigo'] = codigo
    gdf_healpix['zona'] = zona
    
    list_gdf.append(gdf_healpix)
    

gdf_all = pd.concat(list_gdf, ignore_index=True)
gdf_all = gpd.GeoDataFrame(gdf_all, geometry='geometry', crs=list_gdf[0].crs)
gdf_all.to_file("data/procesado/grilla/areas_grilla_healpix.geojson", driver="GeoJSON")


## Plot
# fig, ax = plt.subplots(figsize=(12, 10))
# list_gdf[0].plot(ax=ax, facecolor='none', edgecolor='gray', linewidth=0.5, label='Grilla HEALPix')

# ax.set_title("grilla HEALPix")
# plt.axis('equal')
# plt.show()