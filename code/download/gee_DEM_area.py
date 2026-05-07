import argparse
import os
from glob import glob

import ee
import geemap
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy
from shapely.geometry import box

from code.download.config import DEM_DIR, get_event
from code.download.gee_utils import initialize_gee


RAW_DEM_DIR = "data/dem"


def crear_grilla(bounds, n_cols=2, n_rows=2):
    """Divide un area en una grilla rectangular para descargar desde GEE."""
    xmin, ymin, xmax, ymax = bounds
    width = (xmax - xmin) / n_cols
    height = (ymax - ymin) / n_rows
    grid = []
    for i in range(n_cols):
        for j in range(n_rows):
            x1 = xmin + i * width
            x2 = x1 + width
            y1 = ymin + j * height
            y2 = y1 + height
            grid.append(box(x1, y1, x2, y2))
    return gpd.GeoDataFrame(geometry=grid, crs="EPSG:4326")


def per_img(img):
    """Agrega DEM, slope y aspect a una imagen."""
    terrain = ee.Terrain.products(img)
    return ee.Image.cat([img.rename("DEM"), terrain.select(["slope", "aspect"])])


def raster_centroids_to_gdf(path_tif: str) -> gpd.GeoDataFrame:
    """Convierte un GeoTIFF multibanda a puntos con valores por banda."""
    with rasterio.open(path_tif) as src:
        data = src.read()
        transform = src.transform
        crs = src.crs
        height, width = src.height, src.width
        nodata = src.nodata

        n_bands = data.shape[0]
        names = list(src.descriptions) if src.descriptions else [None] * n_bands
        names = [name or f"band{i + 1}" for i, name in enumerate(names)]

        rows = np.arange(height)
        cols = np.arange(width)
        rr, cc = np.meshgrid(rows, cols, indexing="ij")
        xs, ys = xy(transform, rr, cc, offset="center")
        xs = np.asarray(xs).reshape(height, width)
        ys = np.asarray(ys).reshape(height, width)

        valid = np.ones((height, width), dtype=bool)
        for band in data:
            if np.issubdtype(band.dtype, np.floating):
                valid &= ~np.isnan(band)
            if nodata is not None:
                valid &= band != nodata

        cols_data = {names[i]: data[i][valid] for i in range(n_bands)}
        return gpd.GeoDataFrame(
            cols_data,
            geometry=gpd.points_from_xy(xs[valid], ys[valid]),
            crs=crs,
        )


def aggregate_to_viirs_cells(
    gdf: gpd.GeoDataFrame,
    cell_size_m: int = 375,
    col_elev: str = "elevation",
    col_slope: str = "slope",
    col_aspect: str = "aspect",
    flat_thresh_deg: float = 0.5,
    utm_epsg: int | None = None,
) -> gpd.GeoDataFrame:
    """Agrega elevacion, pendiente y orientacion a celdas cuadradas."""
    if utm_epsg is None:
        utm_epsg = gdf.estimate_utm_crs().to_epsg()
    g = gdf[[col_elev, col_slope, col_aspect, "geometry"]].copy().to_crs(utm_epsg)

    for col in (col_elev, col_slope, col_aspect):
        g[col] = g[col].astype("float32")

    g["__ix"] = (g.geometry.x.values // cell_size_m).astype(np.int64)
    g["__iy"] = (g.geometry.y.values // cell_size_m).astype(np.int64)

    valid_aspect = g[col_slope].gt(flat_thresh_deg) & g[col_aspect].between(0.0, 360.0)
    a_rad = np.deg2rad(g.loc[valid_aspect, col_aspect].astype("float32"))
    g["northness"] = np.nan
    g["eastness"] = np.nan
    g.loc[valid_aspect, "northness"] = np.cos(a_rad).astype("float32")
    g.loc[valid_aspect, "eastness"] = np.sin(a_rad).astype("float32")

    def q90(series: pd.Series) -> float:
        return float(series.quantile(0.9)) if len(series) else np.nan

    agg = g.groupby(["__ix", "__iy"]).agg(
        elev_mean=(col_elev, "mean"),
        elev_std=(col_elev, "std"),
        elev_min=(col_elev, "min"),
        elev_max=(col_elev, "max"),
        slope_mean=(col_slope, "mean"),
        slope_std=(col_slope, "std"),
        slope_p90=(col_slope, q90),
        n_points=(col_elev, "size"),
        north_mean=("northness", "mean"),
        east_mean=("eastness", "mean"),
    ).reset_index()

    agg["elev_range"] = (agg["elev_max"] - agg["elev_min"]).astype("float32")
    east = agg.pop("east_mean").astype("float64")
    north = agg.pop("north_mean").astype("float64")
    agg["aspect_mean"] = ((np.degrees(np.arctan2(east, north)) + 360.0) % 360.0).astype("float32")
    agg["aspect_R"] = np.sqrt(east**2 + north**2).astype("float32")

    cx = (agg["__ix"].to_numpy() + 0.5) * cell_size_m
    cy = (agg["__iy"].to_numpy() + 0.5) * cell_size_m
    geometry = gpd.points_from_xy(cx, cy, crs=f"EPSG:{utm_epsg}")
    return gpd.GeoDataFrame(
        agg.drop(columns=["__ix", "__iy"]),
        geometry=geometry,
        crs=f"EPSG:{utm_epsg}",
    ).to_crs(gdf.crs)


def download_dem_tiles(event_name: str, area_path, n_cols=2, n_rows=2) -> None:
    gdf = gpd.read_file(area_path).to_crs("EPSG:4326")
    tiles = gpd.overlay(crear_grilla(gdf.total_bounds, n_cols, n_rows), gdf, how="intersection")
    os.makedirs(RAW_DEM_DIR, exist_ok=True)
    tiles.to_file(f"{RAW_DEM_DIR}/tiles_dividido_{event_name}.geojson")

    collection = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM")
    for i, tile in tiles.iterrows():
        geom = geemap.geopandas_to_ee(gpd.GeoDataFrame([tile], crs="EPSG:4326"))
        terrain = collection.map(per_img).mosaic().clip(geom)
        img_export = terrain.unmask(-9999).toFloat()
        out_path = f"{RAW_DEM_DIR}/dem_{event_name}_{i}.tif"
        print("Guardando info:", out_path)
        geemap.ee_export_image(
            img_export,
            filename=out_path,
            region=geom.geometry(),
            scale=30,
            file_per_band=False,
        )


def build_dem_outputs(event_name: str, cell_sizes=(375, 100, 50)) -> None:
    rutas_tif = sorted(glob(os.path.join(RAW_DEM_DIR, event_name, f"dem_{event_name}_*.tif")))
    if not rutas_tif:
        raise FileNotFoundError(f"No se encontraron TIFs para {event_name} en {RAW_DEM_DIR}")

    lista_gdf = []
    for path in rutas_tif:
        print("Leyendo ruta:", path)
        lista_gdf.append(raster_centroids_to_gdf(path))

    gdf_final = pd.concat(lista_gdf, ignore_index=True)
    gdf_final = gdf_final.rename(
        columns={
            "band1": "elevacion",
            "DEM": "elevacion",
            "dem": "elevacion",
            "elevation": "elevacion",
            "band2": "slope",
            "band3": "aspect",
        }
    )
    required = {"elevacion", "slope", "aspect"}
    missing = required - set(gdf_final.columns)
    if missing:
        raise ValueError(f"Faltan columnas DEM esperadas: {sorted(missing)}")
    
    ## limpieza de obs
    gdf_final = gdf_final[~gdf_final.eval("elevacion == -9999 & slope == -9999 & aspect == -9999")]
    gdf_final.loc[gdf_final["elevacion"].between(-5, 0), "elevacion"] = 0.0
    gdf_final = gdf_final.loc[~(gdf_final["slope"] <= -9999)]

    DEM_DIR.mkdir(parents=True, exist_ok=True)
    gdf_final.to_file(DEM_DIR / f"DEM_{event_name}.geojson")

    for cell_size in cell_sizes:
        gdf_cell = aggregate_to_viirs_cells(gdf_final, col_elev="elevacion", cell_size_m=cell_size)
        gdf_cell.to_file(DEM_DIR / f"DEM_{event_name}_{cell_size}.geojson")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga y procesa DEM por area")
    parser.add_argument("--event", default="santa_ana", help="Evento definido en config.py")
    parser.add_argument("--skip-download", action="store_true", help="Usar TIFs ya descargados")
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--rows", type=int, default=2)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    event = get_event(args.event)
    initialize_gee()
    if not args.skip_download:
        download_dem_tiles(event.name, event.area_path, args.cols, args.rows)
    build_dem_outputs(event.name)


if __name__ == "__main__":
    main()
