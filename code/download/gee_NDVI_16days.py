import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from datetime import datetime, timedelta

import geemap
import os

ee.Authenticate()  
ee.Initialize(project='tesis-incendios')


##############################################
# functions ----------------------------------

def _points_from_image(img, region, scale=500, band='NDVI', phase='DURANTE'):
    start = ee.Date(img.get('system:time_start'))               # inicio 
    end_excl = start.advance(16, 'day')                         # fin exclusivo (16 días exactos)
    center = start.advance(8, 'day')                            # centro 

    fc = (img.select(band)
            .sample(region=region, scale=scale, geometries=True))

    fc = fc.map(lambda f: f.set({
        'NDVI': f.get(band),
        'img_id': img.get('system:index'),
        'time_start': start.format('YYYY-MM-dd'),
        'time_end': end_excl.format('YYYY-MM-dd'),
        'center_date': center.format('YYYY-MM-dd'),
        'phase': phase
    }))
    return fc


def viirs_ndvi_points_onefile(aoi_geom, start_date, end_date,
                              out_geojson='NDVI_points.geojson',
                              collection_id='NASA/VIIRS/002/VNP13A1',
                              scale=500,
                              include_prev=True):
    """
    Exporta TODOS los centroides (puntos) NDVI de VIIRS 16-d (VNP13A1) a UN solo GeoJSON.
    - include_prev=True: agrega el compuesto previo (último antes de start_date) con phase='PREVIO'
    - DURANTE: todos los compuestos cuya fecha nominal cae entre [start_date, end_date]
    """
    col = (ee.ImageCollection(collection_id)
           .filterBounds(aoi_geom)
           .select('NDVI'))

    # DURANTE (coleccion temporal ordenada por fecha nominal)
    during = col.filterDate(start_date, end_date).sort('system:time_start')

    # Aplana todos los compuestos DURANTE en una sola FeatureCollection
    ids = during.aggregate_array('system:index')
    def _id_to_points(sid):
        sid = ee.String(sid)
        img = ee.Image(during.filter(ee.Filter.eq('system:index', sid)).first())
        return _points_from_image(img, aoi_geom, scale=scale, band='NDVI', phase='DURANTE')
    fc_during = ee.FeatureCollection(ids.map(_id_to_points)).flatten()

    # PREVIO (opcional): último compuesto ANTES de start_date
    if include_prev:
        prev_img = (col.filterDate('1900-01-01', start_date)
                      .sort('system:time_start', False)
                      .first())
        fc_prev = ee.FeatureCollection([])
        fc_prev = ee.Algorithms.If(
            prev_img,
            _points_from_image(ee.Image(prev_img), aoi_geom, scale=scale, band='NDVI', phase='PREVIO'),
            ee.FeatureCollection([])
        )
        fc_prev = ee.FeatureCollection(fc_prev)
        fc_all = fc_prev.merge(fc_during)
    else:
        fc_all = fc_during

    # Exporta TODO a un único GeoJSON
    os.makedirs(os.path.dirname(out_geojson) or ".", exist_ok=True)
    print(f'→ Exportando {out_geojson}')
    geemap.ee_export_vector(fc_all, filename=out_geojson)
    print('✅ Listo:', os.path.abspath(out_geojson))





########################
## load area del incendio
incendio = 'las_maquinas'#'santa_ana_2023'
path_area = f"data/procesado/areas/{incendio}.geojson" 
gdf = gpd.read_file(path_area)
gdf = gdf.to_crs("EPSG:4326")

aoi_geom = geemap.geopandas_to_ee(gpd.GeoDataFrame(gdf, crs="EPSG:4326"))

## load fecha incendio
start_date = datetime(2017, 1, 15)
end_date = datetime(2017, 2, 5) 

# start_date = datetime(2023, 1, 29)
# end_date = datetime(2023, 3, 6)

gdf_out = viirs_ndvi_points_onefile(
    aoi_geom=aoi_geom,
    start_date=start_date,
    end_date=end_date,
    out_geojson='data/NDVI/las_maquinas_NDVI_points_v2.geojson',
    scale=500,               
    include_prev=True      
)


gdf_out = gpd.read_file('data/NDVI/las_maquinas_NDVI_points_v2.geojson')

gdf_out.img_id.value_counts()
gdf_out.time_start.value_counts()
gdf_out.time_end.value_counts()
gdf_out.center_date.value_counts()



