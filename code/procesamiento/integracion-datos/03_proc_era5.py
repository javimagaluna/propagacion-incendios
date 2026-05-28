"""procesamiento inicial de variables de ERA5 (en su resolucion original)"""

import geemap
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# func -----------------------------------------------------------------------------------
def calcular_humedad_relativa(T, Td):
    """
    Se usa la formula para presión de vapor saturado. 
    Estimamos la proporción de la capacidad total de vapor de agua que está efectivamente ocupada.
    
    Args:
        - Las temperaturas deben estar en °C
    """
    return 100 * (np.exp((17.625 * Td) / (243.04 + Td)) /
                  np.exp((17.625 * T) / (243.04 + T)))


## LOAD DATA -----------
INCENDIO = 'santa_ana' #'las_maquinas'
gdf_era5 = gpd.read_file(f'data/procesado/era5/era5_{INCENDIO}_puntos_9km.geojson') 


# VARIABLES DE VIENTO --------------------------------------------------------------------
## esitmacion velocidad del viento (m/s)

gdf_era5['wind_speed'] = np.sqrt(gdf_era5['u_component_of_wind_10m']**2 +
                                 gdf_era5['v_component_of_wind_10m']**2)

## estimacion direccion del viento 
### en grados desde el norte metereologico: se refiere de donde viene el viento N:=0°
gdf_era5['wind_dir'] = (np.degrees(np.arctan2(-gdf_era5['u_component_of_wind_10m'],
                                              -gdf_era5['v_component_of_wind_10m'])) % 360)


# HUMEDAD RELATIVA  -----------------------------------------------------------------------

gdf_era5['temperature_C'] = gdf_era5['temperature_2m'] - 273.15
gdf_era5['dewpoint_C'] = gdf_era5['dewpoint_temperature_2m'] - 273.15

gdf_era5['humidity_percent'] = calcular_humedad_relativa(gdf_era5['temperature_C'], gdf_era5['dewpoint_C'])


# SAVE DATA -----------
gdf_era5.to_file(f'data/procesado/era5/era5_variables_{INCENDIO}_9km.geojson')





### plot -------------------------------------------------------------------------------------
# gdf = gdf_era5[gdf_era5['date_time'] == '2023-03-06 18:30:00']
# gdf['lon'] = gdf.geometry.x
# gdf['lat'] = gdf.geometry.y

# x = gdf['lon'].values
# y = gdf['lat'].values

# u = gdf['u_component_of_wind_10m'].values
# v = gdf['v_component_of_wind_10m'].values

# fig, ax = plt.subplots(figsize=(10, 10))

# # Vectores con color por velocidad
# quiv = ax.quiver(
#     x, y, u, v,
#     gdf['wind_speed'], 
#     cmap='viridis',
#     scale=40,         # tamano flecha
#     width=0.003,      # grosor de las flechas
#     pivot='middle'    # centro de cada flecha es el punto
# )

# cb = fig.colorbar(quiv, ax=ax)
# cb.set_label('Velocidad del viento (m/s)')

# ax.set_title('Vectores de viento ERA5')
# ax.set_xlabel('Longitud')
# ax.set_ylabel('Latitud')
# ax.set_aspect('equal')
# ax.grid(True)

# plt.show()

