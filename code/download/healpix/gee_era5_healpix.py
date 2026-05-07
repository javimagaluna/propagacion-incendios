import argparse
from pathlib import Path

import ee
import geemap
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from code.download.config import ERA5_DIR, ERA5_VARIABLES, HEALPIX_GRID_PATH, SATELLITE_UNION_DIR
from code.download.gee_utils import initialize_gee



def process_era5_cells(fecha_objetivo, fc, variables=None):
    """Descarga ERA5-Land Hourly desde GEE reducido sobre una grilla."""
    if isinstance(fecha_objetivo, str):
        fecha_objetivo = ee.Date(fecha_objetivo)

    variables = variables or ERA5_VARIABLES
    era5 = (
        ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
        .filterDate(fecha_objetivo, fecha_objetivo.advance(1, "hour"))
        .select(variables)
        .first()
    )

    fc_reduced = era5.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=9000,
    )
    df = geemap.ee_to_df(fc_reduced)
    df["date_time"] = pd.to_datetime(fecha_objetivo.getInfo()["value"] / 1000, unit="s", utc=True)
    return df


def intersect_ponderado_area(gdf_fecha, area_filtrado, variables=None):
    """Pondera valores ERA5 por area de interseccion sobre celdas HealPix."""
    variables = variables or ERA5_VARIABLES
    crs_proj = area_filtrado.estimate_utm_crs()
    gdf_fecha_proj = gdf_fecha.to_crs(crs_proj)
    area_filtrado_proj = area_filtrado.to_crs(crs_proj)

    inter = gpd.overlay(area_filtrado_proj, gdf_fecha_proj, how="intersection")
    inter["area_inter"] = inter.geometry.area
    area_filtrado_proj["area_celda"] = area_filtrado_proj.geometry.area

    if "area_celda" in inter.columns:
        inter = inter.drop(columns=["area_celda"])
    inter = inter.merge(area_filtrado_proj[["Codigo", "area_celda"]], on="Codigo", how="left")
    inter["peso"] = inter["area_inter"] / inter["area_celda"]

    for var in variables:
        inter[f"{var}_pond"] = inter[var] * inter["peso"]

    agregados = inter.groupby("Codigo")[[f"{var}_pond" for var in variables]].sum().reset_index()
    suma_pesos = inter.groupby("Codigo")["peso"].sum().reset_index().rename(columns={"peso": "peso_total"})
    agregados = agregados.merge(suma_pesos, on="Codigo", how="left")

    for var in variables:
        agregados[f"{var}_ponderado"] = agregados[f"{var}_pond"] / agregados["peso_total"]

    return area_filtrado.merge(
        agregados[["Codigo"] + [f"{var}_ponderado" for var in variables]],
        on="Codigo",
        how="left",
    )


def load_satellite_dates() -> pd.DataFrame:
    frames = []
    for satellite in ("noaa1", "noaa2", "suomi"):
        path = SATELLITE_UNION_DIR / f"zonas_{satellite}.geojson"
        frames.append(gpd.read_file(path)[["zona", "date_time"]].drop_duplicates())

    fechas = pd.concat(frames, ignore_index=True)
    fechas["fecha_gee"] = fechas.date_time.dt.strftime("%Y-%m-%dT%H:00")
    return fechas


def make_utm_grid(gdf_zona, grid_size=1035):
    gdf_zona_utm = gdf_zona.to_crs(gdf_zona.estimate_utm_crs())
    minx, miny, maxx, maxy = gdf_zona_utm.total_bounds

    grid_polygons = []
    x_left = minx
    while x_left < maxx:
        y_bottom = miny
        while y_bottom < maxy:
            grid_polygons.append(box(x_left, y_bottom, x_left + grid_size, y_bottom + grid_size))
            y_bottom += grid_size
        x_left += grid_size

    grid_gdf = gpd.GeoDataFrame({"geometry": grid_polygons}, crs=gdf_zona_utm.crs)
    grid_gdf["id"] = range(grid_gdf.shape[0])
    return grid_gdf


def download_zone_grids(areas, fechas_gen, zones, output_dir=ERA5_DIR, grid_size=1035):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for zona in zones:
        print(f"{zona} --------------------")
        fechas = fechas_gen[fechas_gen["zona"] == zona]["fecha_gee"].unique()
        gdf_zona = areas[areas["zona"] == zona]
        grid_gdf = make_utm_grid(gdf_zona, grid_size=grid_size)
        fc = geemap.geopandas_to_ee(grid_gdf)

        lista_gdf = []
        for fecha in fechas:
            print(fecha)
            df = process_era5_cells(fecha, fc)
            df = grid_gdf.merge(df, on="id", how="left")
            print(df.isna().sum())
            lista_gdf.append(df)

        if not lista_gdf:
            continue

        gdf_final = pd.concat(lista_gdf, ignore_index=True)
        gdf_final = gpd.GeoDataFrame(gdf_final, geometry="geometry", crs=lista_gdf[0].crs).drop(["id"], axis=1)
        gdf_final.to_file(output_dir / f"info_era5_{zona}_grilla.geojson")


def add_weather_derived_columns(gdf):
    gdf = gdf.copy()
    u = gdf["u_component_of_wind_10m_ponderado"]
    v = gdf["v_component_of_wind_10m_ponderado"]
    td_k = gdf["dewpoint_temperature_2m_ponderado"]
    t_k = gdf["temperature_2m_ponderado"]

    gdf["wind_speed_10m"] = (u**2 + v**2) ** 0.5
    gdf["wind_dir_10m"] = (np.degrees(np.arctan2(-u, -v)) + 360) % 360

    es_td = 6.112 * np.exp((17.67 * (td_k - 273.15)) / (td_k - 29.65))
    es_t = 6.112 * np.exp((17.67 * (t_k - 273.15)) / (t_k - 29.65))
    gdf["relative_humidity"] = 100 * es_td / es_t
    gdf["VPD"] = es_t - es_td
    gdf["temperature_2m_C"] = t_k - 273.15
    gdf["dewpoint_temperature_2m_C"] = td_k - 273.15
    return gdf


def build_healpix_outputs(areas, zones, output_dir=ERA5_DIR):
    output_dir = Path(output_dir)
    for zona in zones:
        print(f"{zona} ---------------------")
        gdf = gpd.read_file(output_dir / f"info_era5_{zona}_grilla.geojson")
        area_filtrado = areas[areas["zona"] == zona]

        lista_gdf = []
        for fecha in gdf["date_time"].unique():
            print(fecha)
            gdf_fecha = gdf[gdf["date_time"] == fecha]
            gdf_inter = intersect_ponderado_area(gdf_fecha, area_filtrado)
            gdf_inter["date_time"] = fecha
            lista_gdf.append(add_weather_derived_columns(gdf_inter))

        if not lista_gdf:
            continue

        gdf_final = pd.concat(lista_gdf, ignore_index=True)
        gdf_final = gpd.GeoDataFrame(gdf_final, geometry="geometry", crs=lista_gdf[0].crs)
        gdf_final.to_file(output_dir / f"era5_{zona}_healpix.geojson")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga ERA5 y lo pondera a grilla HealPix")
    parser.add_argument("--zones", nargs="*", default=None, help="Zonas a procesar; por defecto todas")
    parser.add_argument("--skip-download", action="store_true", help="Usar grillas ERA5 ya descargadas")
    parser.add_argument("--grid-size", type=int, default=1035)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    initialize_gee()
    areas = gpd.read_file(HEALPIX_GRID_PATH)
    zones = args.zones or sorted(areas["zona"].unique())

    if not args.skip_download:
        fechas_gen = load_satellite_dates()
        download_zone_grids(areas, fechas_gen, zones, grid_size=args.grid_size)

    build_healpix_outputs(areas, zones)


if __name__ == "__main__":
    main()
