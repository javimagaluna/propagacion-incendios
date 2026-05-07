import argparse

import ee
import geemap
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from code.download.config import ERA5_DIR, SATELLITE_UNION_DIR, get_event
from code.download.gee_utils import initialize_gee


ERA5_BANDS = [
    "temperature_2m",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "dewpoint_temperature_2m",
]


def crear_grilla_regular(gdf, geometry, resolucion_m=9000):
    bounds = gdf.total_bounds
    xmin, ymin, xmax, ymax = bounds
    resolucion_grados = resolucion_m / 111320

    puntos = []
    id_counter = 0
    y = ymin
    while y <= ymax:
        x = xmin
        while x <= xmax:
            point = Point(x, y)
            if geometry.contains(point):
                puntos.append({"id": id_counter, "geometry": point})
                id_counter += 1
            x += resolucion_grados
        y += resolucion_grados

    return gpd.GeoDataFrame(puntos, crs="EPSG:4326")


def get_era5_land_hourly(grilla_ee, fecha, scale=9000):
    if isinstance(fecha, str):
        fecha = ee.Date(fecha)

    era5 = (
        ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
        .filterDate(fecha, fecha.advance(1, "hour"))
        .select(ERA5_BANDS)
        .first()
    )

    muestra = era5.sampleRegions(collection=grilla_ee, scale=scale, geometries=True)
    df = geemap.ee_to_df(muestra)
    df["date_download"] = pd.to_datetime(fecha.getInfo()["value"] / 1000, unit="s", utc=True)
    return df


def load_unique_dates(event_name: str, satellite: str) -> pd.Series:
    data = gpd.read_file(SATELLITE_UNION_DIR / f"{satellite}_{event_name}.geojson")
    return data["date_time"].drop_duplicates().reset_index(drop=True)


def run(event_name: str, satellite: str, area_path, resolution_m=9000) -> None:
    fechas = load_unique_dates(event_name, satellite)
    gdf = gpd.read_file(area_path).to_crs("EPSG:4326")
    geometry = gdf.union_all() if hasattr(gdf, "union_all") else gdf.unary_union
    grilla = crear_grilla_regular(gdf, geometry=geometry, resolucion_m=resolution_m)

    features = [
        ee.Feature(ee.Geometry.Point([row.geometry.x, row.geometry.y]), {"id": int(row.id)})
        for _, row in grilla.iterrows()
    ]
    grilla_ee = ee.FeatureCollection(features)

    lista_gdf = []
    for fecha in fechas:
        print(fecha)
        fecha_obj = fecha.strftime("%Y-%m-%dT%H:00")
        aux = get_era5_land_hourly(grilla_ee=grilla_ee, fecha=fecha_obj, scale=resolution_m)
        aux["date_time"] = fecha
        aux_geo = grilla.merge(aux, on="id", how="left")
        print("Valores NA:", aux_geo.isna().sum())
        lista_gdf.append(aux_geo.dropna())

    if not lista_gdf:
        raise ValueError("No hay fechas para procesar.")

    gdf_final = pd.concat(lista_gdf, ignore_index=True)
    gdf_final = gpd.GeoDataFrame(gdf_final, geometry="geometry", crs=lista_gdf[0].crs).drop(["id"], axis=1)

    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    gdf_final.to_file(ERA5_DIR / f"era5_{event_name}_puntos_{resolution_m // 1000}km.geojson")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga ERA5 sobre una grilla regular de puntos")
    parser.add_argument("--event", default="santa_ana", help="Evento definido en config.py")
    parser.add_argument("--satellite", default="suomi")
    parser.add_argument("--resolution-m", type=int, default=9000)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    event = get_event(args.event)
    initialize_gee()
    run(event.name, args.satellite, event.area_path, args.resolution_m)


if __name__ == "__main__":
    main()
