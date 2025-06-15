import rasterio
import pandas as pd
import numpy as np
from tqdm import tqdm
import geopandas as gpd
from shapely.geometry import Point


gdf = gpd.read_file("data/procesado/grilla/areas_grilla_healpix_id_num.geojson")

path = 'data/raw/DEM'
path_save = 'data/procesado/DEM'

zonas = gdf['zona'].unique()
for zona in zonas:
    print(zona)
    with rasterio.open(f"{path}/DEM_{zona}.tif") as dem_src, \
        rasterio.open(f"{path}/Slope_{zona}.tif") as slope_src, \
        rasterio.open(f"{path}/Aspect_{zona}.tif") as aspect_src, \
        rasterio.open(f"{path}/ID_{zona}.tif") as id_src:

        dem = dem_src.read(1)
        slope = slope_src.read(1)
        aspect = aspect_src.read(1)
        ids = id_src.read(1)
        transform = dem_src.transform
        nodata = dem_src.nodata
        
    min_rows = min(dem.shape[0], slope.shape[0], aspect.shape[0], ids.shape[0])
    min_cols = min(dem.shape[1], slope.shape[1], aspect.shape[1], ids.shape[1])

    dem = dem[:min_rows, :min_cols]
    slope = slope[:min_rows, :min_cols]
    aspect = aspect[:min_rows, :min_cols]
    ids = ids[:min_rows, :min_cols]

    # filtramos validos
    mask = (ids > 0) & (dem != nodata) & (slope != nodata) & (aspect != nodata)
    rows, cols = np.where(mask)

    dem_vals = dem[rows, cols]
    slope_vals = slope[rows, cols]
    aspect_vals = aspect[rows, cols]
    id_vals = ids[rows, cols].astype(int)

    # coords
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    geometry = [Point(x, y) for x, y in zip(xs, ys)]
    id_dict = dict(zip(gdf['id_num'], gdf['Codigo']))

    codigo_vals = [id_dict[i] for i in id_vals]
    
    gdf_pix = gpd.GeoDataFrame({
                'Codigo': codigo_vals,
                'id_num': id_vals,
                'elev': dem_vals,
                'slope': slope_vals,
                'aspect': aspect_vals
                }, geometry=geometry, crs="EPSG:4326")
    gdf_pix.to_file(f'{path_save}/{zona}.geojson', driver="GeoJSON")