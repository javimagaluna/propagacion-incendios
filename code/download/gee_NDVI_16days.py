import argparse
import os

import ee
import geemap
import geopandas as gpd

from code.download.config import NDVI_DIR, get_event
from code.download.gee_utils import initialize_gee



def _points_from_image(img, region, scale=500, band="NDVI", phase="DURANTE"):
    start = ee.Date(img.get("system:time_start"))
    end_excl = start.advance(16, "day")
    center = start.advance(8, "day")

    fc = img.select(band).sample(region=region, scale=scale, geometries=True)
    return fc.map(
        lambda f: f.set(
            {
                "NDVI": f.get(band),
                "img_id": img.get("system:index"),
                "time_start": start.format("YYYY-MM-dd"),
                "time_end": end_excl.format("YYYY-MM-dd"),
                "center_date": center.format("YYYY-MM-dd"),
                "phase": phase,
            }
        )
    )


def viirs_ndvi_points_onefile(
    aoi_geom,
    start_date,
    end_date,
    out_geojson="NDVI_points.geojson",
    collection_id="NASA/VIIRS/002/VNP13A1",
    scale=500,
    include_prev=True,
):
    """Exporta centroides NDVI VIIRS 16-d a un GeoJSON."""
    col = ee.ImageCollection(collection_id).filterBounds(aoi_geom).select("NDVI")
    during = col.filterDate(start_date, end_date).sort("system:time_start")

    ids = during.aggregate_array("system:index")

    def _id_to_points(sid):
        sid = ee.String(sid)
        img = ee.Image(during.filter(ee.Filter.eq("system:index", sid)).first())
        return _points_from_image(img, aoi_geom, scale=scale, band="NDVI", phase="DURANTE")

    fc_during = ee.FeatureCollection(ids.map(_id_to_points)).flatten()

    if include_prev:
        prev_img = col.filterDate("2010-01-01", start_date).sort("system:time_start", False).first()
        fc_prev = ee.Algorithms.If(
            prev_img,
            _points_from_image(ee.Image(prev_img), aoi_geom, scale=scale, band="NDVI", phase="PREVIO"),
            ee.FeatureCollection([]),
        )
        fc_all = ee.FeatureCollection(fc_prev).merge(fc_during)
    else:
        fc_all = fc_during

    os.makedirs(os.path.dirname(out_geojson) or ".", exist_ok=True)
    print(f"Exportando {out_geojson}")
    geemap.ee_export_vector(fc_all, filename=out_geojson)
    print("Listo:", os.path.abspath(out_geojson))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga NDVI VIIRS 16 dias desde GEE")
    parser.add_argument("--event", default="santa_ana", help="Evento definido en config.py")
    parser.add_argument("--output", default=None, help="GeoJSON de salida opcional")
    parser.add_argument("--scale", type=int, default=500)
    parser.add_argument("--no-prev", action="store_true", help="No incluir compuesto previo")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    event = get_event(args.event)
    initialize_gee()

    gdf = gpd.read_file(event.area_path).to_crs("EPSG:4326")
    aoi_geom = geemap.geopandas_to_ee(gdf)
    output = args.output or str(NDVI_DIR / f"{event.name}_NDVI_points.geojson")

    viirs_ndvi_points_onefile(
        aoi_geom=aoi_geom,
        start_date=event.start_iso,
        end_date=event.end_iso,
        out_geojson=output,
        scale=args.scale,
        include_prev=not args.no_prev,
    )


if __name__ == "__main__":
    main()
