"""
Etapa 01: convierte pares NetCDF VIIRS (bandas + coordenadas) a GeoJSON.

Output:
    data/procesado/satellite_data/{incendio}/{satelite}/merge_{clave}_{incendio}.geojson

Esta salida es el insumo de 02_procesamiento_filtro_VIIRS.py.
"""

from pathlib import Path
import re
import warnings

import geopandas as gpd
import pandas as pd
import rioxarray
from rasterio.errors import NotGeoreferencedWarning
import xarray as xr


warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


# Config ---------------------------------------------------------------------------
INCENDIO = "las_maquinas"
SATELITE = "SUOMI"

PATRON_CLAVE_VIIRS = re.compile(r"A\d{7}\.\d{4}\.\d{3}")

PATH_AREAS = Path(f"data/procesado/areas/{INCENDIO}.geojson")
PATH_BANDAS = Path(f"datos-viirs/{SATELITE}/{INCENDIO}/BANDAS")
PATH_COORDS = Path(f"datos-viirs/{SATELITE}/{INCENDIO}/COORDS")
PATH_SALIDA = Path(f"data/procesado/satellite_data/{INCENDIO}/{SATELITE}")


# Func ------------------------------------------------------------------------------
def extraer_clave_viirs(path_archivo):
    """Extrae la clave orbital VIIRS desde el nombre del archivo."""
    match = PATRON_CLAVE_VIIRS.search(path_archivo.name)
    return match.group() if match else None


def listar_archivos_por_clave(carpeta):
    """Lista archivos NetCDF indexados por clave VIIRS."""
    return {
        clave: path_archivo
        for path_archivo in carpeta.glob("*.nc")
        if (clave := extraer_clave_viirs(path_archivo))
    }


def identificar_pares_nc(path_bandas, path_coords):
    """Identifica pares banda-coordenada disponibles para la misma clave VIIRS."""
    archivos_bandas = listar_archivos_por_clave(path_bandas)
    archivos_coords = listar_archivos_por_clave(path_coords)

    claves_comunes = sorted(archivos_bandas.keys() & archivos_coords.keys())
    pares = [(archivos_bandas[clave], archivos_coords[clave]) for clave in claves_comunes]

    claves_sin_bandas = sorted(archivos_coords.keys() - archivos_bandas.keys())
    claves_sin_coords = sorted(archivos_bandas.keys() - archivos_coords.keys())

    return pares, claves_sin_bandas, claves_sin_coords


def cargar_areas(path_areas, incendio):
    """Carga el poligono de area de interes y lo lleva a WGS84."""
    areas = gpd.read_file(path_areas).to_crs(epsg=4326)
    areas["zona"] = incendio
    return areas


def escalar_variable(data_array):
    """Aplica scale_factor y add_offset cuando vienen en los atributos NetCDF."""
    scale_factor = data_array.attrs.get("scale_factor", 1)
    add_offset = data_array.attrs.get("add_offset", 0)
    return data_array.isel(band=0) * scale_factor + add_offset


def calcular_indice_incertidumbre(data_array):
    """Calcula el indice de incertidumbre VIIRS desde la variable cruda."""
    scale_factor = data_array.attrs["scale_factor"]
    return 1 + scale_factor * (data_array.isel(band=0) ** 2)


def crear_dataset_viirs(path_bandas, path_coords):
    """Crea un Dataset con coordenadas, angulos, bandas y banderas de calidad."""
    coords = rioxarray.open_rasterio(path_coords)
    bandas = rioxarray.open_rasterio(path_bandas)

    coords_img = coords[0]

    return xr.Dataset(
        {
            "latitude": coords_img["latitude"].isel(band=0),
            "longitude": coords_img["longitude"].isel(band=0),
            "sensor_zenith": escalar_variable(coords_img["sensor_zenith"]),
            "sensor_azimuth": escalar_variable(coords_img["sensor_azimuth"]),
            "I04": escalar_variable(bandas["I04"]),
            "I05": escalar_variable(bandas["I05"]),
            "I04_quality_flags": bandas["I04_quality_flags"].isel(band=0),
            "I05_quality_flags": bandas["I05_quality_flags"].isel(band=0),
            "quality_flag": coords_img["quality_flag"].isel(band=0),
            "I04_uncert_index": calcular_indice_incertidumbre(bandas["I04_uncert_index"]),
            "I05_uncert_index": calcular_indice_incertidumbre(bandas["I05_uncert_index"]),
        }
    )


def dataset_a_geodataframe(dataset):
    """Transforma el Dataset VIIRS a GeoDataFrame de puntos."""
    df = dataset.to_dataframe().reset_index()
    df = df.dropna(subset=["latitude", "longitude"])
    df = df.drop(columns=["x", "y", "band", "spatial_ref"], errors="ignore")

    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )


def filtrar_por_areas(gdf, areas):
    """Mantiene puntos que intersectan las areas de interes y asigna su zona."""
    gdfs_filtrados = []

    for _, area in areas.iterrows():
        gdf_filtrado = gdf[gdf.geometry.intersects(area.geometry)].copy()
        gdf_filtrado["zona"] = area["zona"]
        gdfs_filtrados.append(gdf_filtrado)

    if not gdfs_filtrados:
        return gpd.GeoDataFrame(columns=gdf.columns.tolist() + ["zona"], crs=gdf.crs)

    return gpd.GeoDataFrame(pd.concat(gdfs_filtrados, ignore_index=True), crs=gdf.crs)


def procesar_par(path_bandas, path_coords, areas, path_salida, incendio):
    """Procesa un par NetCDF y guarda su GeoJSON filtrado por area."""
    clave = extraer_clave_viirs(path_bandas)
    archivo_salida = path_salida / f"merge_{clave}_{incendio}.geojson"

    print("-----------")
    print(clave)

    if archivo_salida.exists():
        print(f"Archivo ya existe: {archivo_salida}")
        return

    dataset = crear_dataset_viirs(path_bandas, path_coords)
    gdf = dataset_a_geodataframe(dataset)
    gdf_filtrado = filtrar_por_areas(gdf, areas)
    del gdf    ## liberamos un pichintun de espacio
    if gdf_filtrado.empty:
        print("No hay datos dentro de las zonas")
        return

    print(gdf_filtrado["zona"].value_counts())
    print(gdf_filtrado["I04"].describe())

    print(f"Guardando: {archivo_salida}")
    gdf_filtrado.to_file(archivo_salida, driver="GeoJSON")


def main():
    PATH_SALIDA.mkdir(parents=True, exist_ok=True)

    areas = cargar_areas(PATH_AREAS, INCENDIO)
    pares, claves_sin_bandas, claves_sin_coords = identificar_pares_nc(PATH_BANDAS, PATH_COORDS)

    print(f"Pares encontrados: {len(pares)}")
    if claves_sin_bandas:
        print(f"Claves sin bandas: {len(claves_sin_bandas)}")
    if claves_sin_coords:
        print(f"Claves sin coordenadas: {len(claves_sin_coords)}")

    for path_bandas, path_coords in pares:
        procesar_par(path_bandas, path_coords, areas, PATH_SALIDA, INCENDIO)


if __name__ == "__main__":
    main()
