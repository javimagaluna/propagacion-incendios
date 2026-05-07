import argparse
from pathlib import Path

import ee
import geemap
import geopandas as gpd

from code.download.config import DEM_DIR, HEALPIX_GRID_PATH
from code.download.gee_utils import initialize_gee



def process_image_cells(image, fc, scale=30):
    """Reduce una imagen satelital a promedios por celda de una FeatureCollection."""
    fc_reduced = image.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )
    return geemap.ee_to_df(fc_reduced)


def process_zone_dem(gdf_zone: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    fc = geemap.geopandas_to_ee(gdf_zone)

    dem_image = ee.ImageCollection("COPERNICUS/DEM/GLO30").filterBounds(fc).first().select("DEM")
    df_dem = process_image_cells(dem_image, fc).rename(columns={"mean": "dem"})

    terrain = ee.Terrain.products(dem_image)
    df_slope = process_image_cells(terrain.select("slope"), fc).rename(columns={"mean": "slope"})
    df_aspect = process_image_cells(terrain.select("aspect"), fc).rename(columns={"mean": "aspect"})

    df_merge = (
        df_dem.merge(df_slope, on=["Codigo", "zona"], how="inner")
        .merge(df_aspect, on=["Codigo", "zona"], how="inner")
    )
    return gdf_zone.merge(df_merge, on=["Codigo", "zona"], how="left")


def run(input_grid=HEALPIX_GRID_PATH, output_dir=DEM_DIR, zones=None) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.read_file(input_grid)
    zone_names = zones or sorted(gdf["zona"].unique())

    for zone in zone_names:
        print(f"Procesando zona: {zone}")
        gdf_zone = gdf[gdf["zona"] == zone]
        out = process_zone_dem(gdf_zone)
        out.to_file(output_dir / f"dem_{zone}.geojson")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reduce DEM, slope y aspect sobre grilla HealPix.")
    parser.add_argument("--zones", nargs="*", default=None, help="Zonas a procesar; por defecto todas")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    initialize_gee()
    run(zones=args.zones)


if __name__ == "__main__":
    main()
