from pathlib import Path

import ee
import geemap
import geopandas as gpd

try:
    from .config import GEE_PROJECT
except ImportError:
    from config import GEE_PROJECT


def initialize_gee(project: str = GEE_PROJECT, authenticate: bool = True) -> None:
    """Start an Earth Engine session for scripts that download from GEE."""
    if authenticate:
        ee.Authenticate()
    ee.Initialize(project=project)


def read_area(path: str | Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path).to_crs("EPSG:4326")


def area_to_ee(path: str | Path) -> ee.FeatureCollection:
    gdf = read_area(path)
    return geemap.geopandas_to_ee(gdf)


def ensure_parent_dir(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
