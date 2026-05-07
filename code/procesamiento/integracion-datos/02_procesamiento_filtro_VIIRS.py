"""
Etapa 02: une y filtra los GeoJSON generados en 01_procesamiento_nc_VIIRS.py.

Input:
    data/procesado/satellite_data/{incendio}/{satelite}/merge_*.geojson

Output:
    data/procesado/satellite_data/union/{satelite}_{incendio}.geojson
"""

from datetime import datetime, timedelta
from pathlib import Path
import re

import geopandas as gpd
import pandas as pd


# Config ---------------------------------------------------------------------------
INCENDIO = "santa_ana" #"las_maquinas"
SATELITE = "suomi"
MIN_PIXELES_POR_PASADA = 3700 #10000

PATRON_CLAVE_VIIRS = re.compile(r"A\d{7}\.\d{4}\.\d{3}")

PATH_INPUT = Path(f"data/procesado/satellite_data/{SATELITE}/{INCENDIO}")
PATH_OUTPUT= Path("data/procesado/satellite_data/union") / f"{SATELITE.lower()}_{INCENDIO}.geojson"

# Pasadas con pocos pixeles que se conservan manualmente si aparecen en el incendio.
FECHAS_POCO_DENSAS_A_CONSERVAR = {
    datetime(2023, 2, 12, 17, 48),
}


# Func ------------------------------------------------------------------------------
def extraer_clave_viirs(path_archivo):
    """Extrae la clave orbital VIIRS desde el nombre del archivo"""
    
    match = PATRON_CLAVE_VIIRS.search(path_archivo.name)
    if not match:
        raise ValueError(f"No se encontro clave VIIRS en {path_archivo}")
    return match.group()


def extraer_fecha(clave_viirs):
    """Convierte una clave VIIRS tipo A2023029.0454.002 a datetime"""
    
    anio = int(clave_viirs[1:5])
    dia = int(clave_viirs[5:8])
    hora = int(clave_viirs[9:11])
    minuto = int(clave_viirs[11:13])

    fecha = datetime(anio, 1, 1) + timedelta(days=dia - 1)
    return fecha.replace(hour=hora, minute=minuto)


def listar_geojson_entrada(path_entrada):
    """Lista los archivos generados por la etapa 01"""
    
    archivos = sorted(path_entrada.glob("merge_*.geojson"))
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos merge_*.geojson en {path_entrada}")
    return archivos


def cargar_geojson_viirs(path_archivo):
    """Carga un GeoJSON VIIRS y agrega fecha extraida desde el nombre"""
    
    clave = extraer_clave_viirs(path_archivo)
    gdf = gpd.read_file(path_archivo)
    gdf["date_time"] = extraer_fecha(clave)
    gdf["date_file"] = clave
    return gdf


def unir_archivos_viirs(archivos):
    """Une los GeoJSON VIIRS de la etapa 01 en un solo GeoDataFrame"""
    
    gdfs = []

    for path_archivo in archivos:
        print(path_archivo.name)
        gdfs.append(cargar_geojson_viirs(path_archivo))

    return gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)


def filtrar_calidad(gdf):
    """Elimina pixeles donde ambas bandas termicas tienen bandera de baja calidad"""
    
    mask_baja_calidad = (gdf["I04_quality_flags"] == 256) & (gdf["I05_quality_flags"] == 256)
    return gdf.loc[~mask_baja_calidad].copy()


def filtrar_pasadas_poco_densas(gdf, min_pixeles, fechas_a_conservar):
    """Elimina pasadas con menos pixeles que el minimo configurado"""
    
    conteo_por_fecha = gdf["date_time"].value_counts()
    fechas_poco_densas = set(conteo_por_fecha[conteo_por_fecha < min_pixeles].index)
    fechas_a_eliminar = fechas_poco_densas - set(fechas_a_conservar)

    if fechas_a_eliminar:
        print(f"Pasadas eliminadas por pocos pixeles: {len(fechas_a_eliminar)}")

    return gdf.loc[~gdf["date_time"].isin(fechas_a_eliminar)].copy()


def limpiar_columnas(gdf):
    """Elimina columnas auxiliares que no se usan en etapas posteriores."""
    return gdf.drop(columns=["I04_uncert_index", "I05_uncert_index"], errors="ignore")



def main():
    archivos = listar_geojson_entrada(PATH_INPUT)

    gdf = unir_archivos_viirs(archivos)
    gdf = limpiar_columnas(gdf)
    gdf = filtrar_calidad(gdf)
    gdf = filtrar_pasadas_poco_densas(
        gdf,
        min_pixeles=MIN_PIXELES_POR_PASADA,
        fechas_a_conservar=FECHAS_POCO_DENSAS_A_CONSERVAR,
    )

    PATH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Guardando: {PATH_OUTPUT}")
    gdf.to_file(PATH_OUTPUT, driver="GeoJSON")



if __name__ == "__main__":
    main()










# ### brillo -----------------------
# import numpy as np

# def radiance_to_bt_viirs(radiance, wavelength_microns):
#     # Constantes fisicas ajustadas para VIIRS y la formula de temperatura de brillo en micrómetros
#     h = 6.62607015e-34       # Planck (J·s)
#     c = 2.99792458e8         # velocidad de la luz (m/s)
#     k = 1.380649e-23         # Boltzmann (J/K)
    
#     lambda_m = wavelength_microns * 1e-6  # Convertir micrómetros a metros
#     radiance = np.asarray(radiance)  # asegurarse que es np.array
#     epsilon = 1e-20  # para evitar división por cero

#     # Fórmula exacta: T = (h·c) / (lambda·k·ln[(2·h·c²)/(lambda^5·L) + 1])
#     numerator = h * c
#     denominator = lambda_m * k * np.log((2 * h * c**2) / ((radiance + epsilon) * lambda_m**5) + 1)
    
#     return numerator / denominator  # Resultado en Kelvin


# def calc_bt_planck(L, wavelength_um=3.74):
#     """
#     Calcula la temperatura de brillo
#     """
#     c1 = 1.19104e8  
#     c2 = 1.43877e4  
    
#     epsilon = 1e-10  # para evitar division por cero
#     term = (c1 / (np.maximum(L, epsilon) * wavelength_um**5)) + 1
#     T_b = (c2 / wavelength_um) / np.log(term)
    
#     return T_b


# def calc_bt_planck_fixed(L, wavelength_um=3.74):
#     c1 = 1.19104e8  # W·mu m⁴/(m²·sr)
#     c2 = 1.43877e4  # mu m·K

#     epsilon = 1e-10
#     L = np.maximum(L, epsilon)
#     term = (c1 / (L * wavelength_um**5)) + 1
#     T_b = (c2 * wavelength_um) / np.log(term)
    
#     return T_b

# fixed_i04 = calc_bt_planck_fixed(gdf.I04, 3.74)
# bt_i04_2 = calc_bt_planck(gdf.I04, 3.74)
# bt_i05_2 = calc_bt_planck(gdf.I05, 11.45)

# bt_i04 = radiance_to_bt_viirs(gdf.I04, wavelength_microns=3.74)
# bt_i05 = radiance_to_bt_viirs(gdf.I05, wavelength_microns=11.45)

# gdf['bt_i04'] = bt_i04
# gdf['bt_i05_2'] = bt_i05_2