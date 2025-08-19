import ee

import geemap
import geopandas as gpd
import numpy as np
import pandas as pd

from shapely.geometry import box
import rasterio
from rasterio.transform import xy


import os
from glob import glob

ee.Authenticate()  
ee.Initialize(project='tesis-incendios')

# functions ----------------------------------

def crear_grilla(bounds, n_cols=2, n_rows=2):
    """
    Separa el area en una grilla mas pequeña para que gee pueda realizar la descarga en local.
    Se elige dividir el area en 4 secciones.
    """
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
    """Obtener bandas y unirlas"""
    terr = ee.Terrain.products(img)  # bands: elevation, slope (°), aspect (°)
    # concatena DEM 
    out = ee.Image.cat([
        img.rename("DEM"),
        terr.select(["slope", "aspect"])
    ])
    return out


def raster_centroids_to_gdf(path_tif: str) -> gpd.GeoDataFrame:
    """Convierte un geoTIFF multibanda a puntos + valores por banda"""
    
    with rasterio.open(path_tif) as src:
        data = src.read()            # (bands, H, W)
        transform = src.transform
        crs = src.crs
        H, W = src.height, src.width
        nodata = src.nodata

        # get nombres bandas
        n_bands = data.shape[0]
        names = None
        
        desc = list(src.descriptions) if src.descriptions else []
        if len(desc) == n_bands and any(d for d in desc):
            names = [d if (d is not None and d != "") else None for d in desc]

        # tags por banda (long_name / name)
        if names is None or any(n is None for n in names):
            if names is None:
                names = [None]*n_bands
            filled = []
            for i, n in enumerate(names, start=1):
                if n is not None:
                    filled.append(n)
                    continue
                tags_i = src.tags(i)  # dict
                candidate = tags_i.get("long_name") or tags_i.get("name") or ""
                filled.append(candidate if candidate else None)
            names = filled

        # si no se detectaron nombres, entonces dejar uno por default
        for i in range(n_bands):
            if names[i] is None or names[i] == "":
                names[i] = f"band{i+1}"

        # get coords centroides
        rows = np.arange(H)
        cols = np.arange(W)
        rr, cc = np.meshgrid(rows, cols, indexing="ij")  # (H, W)

        xs2, ys2 = xy(transform, rr, cc, offset="center")
        xs2 = np.asarray(xs2).reshape(H, W)
        ys2 = np.asarray(ys2).reshape(H, W)

        ## nos quedamos con valores validos
        valid = np.ones((H, W), dtype=bool)
        for b in range(n_bands):
            band = data[b]
            if np.issubdtype(band.dtype, np.floating):
                valid &= ~np.isnan(band)
            if nodata is not None:
                valid &= (band != nodata)

        # obtener vectoes
        xv = xs2[valid]
        yv = ys2[valid]
        cols_data = {names[i]: data[i][valid] for i in range(n_bands)}
        rowv, colv = np.where(valid)

        # to geodf 
        df_dict = {**cols_data}

        gdf = gpd.GeoDataFrame(
            df_dict,
            geometry=gpd.points_from_xy(xv, yv),
            crs=crs
        )
        return gdf


def aggregate_to_viirs_cells(
    gdf: gpd.GeoDataFrame,
    cell_size_m: int = 375,
    col_elev: str = "elevation",
    col_slope: str = "slope",
    col_aspect: str = "aspect",
    flat_thresh_deg: float = 0.5,
    utm_epsg: int | None = None
) -> gpd.GeoDataFrame:
    """
    Agrega elevacion, pendiente y aspect a celdas cuadradas de 'cell_size_m' (ej 375 m).
    Devuelve un GeoDataFrame con un punto en el centro de cada celda y estadísticas agregadas.
    """

    # reproyeccion a CRS metrico para interc 
    if utm_epsg is None:
        utm_epsg = gdf.estimate_utm_crs().to_epsg()
    g = gdf[[col_elev, col_slope, col_aspect, "geometry"]].copy()
    g = g.to_crs(utm_epsg)

    for c in (col_elev, col_slope, col_aspect):
        g[c] = g[c].astype("float32")

    x = g.geometry.x.values
    y = g.geometry.y.values
    ix = (x // cell_size_m).astype(np.int64)
    iy = (y // cell_size_m).astype(np.int64)
    g["__ix"] = ix
    g["__iy"] = iy

    # componentes circulares de aspect (solo donde hay pendiente) 
    valid_aspect = (
        g[col_slope].gt(flat_thresh_deg) &
        g[col_aspect].between(0.0, 360.0, inclusive="both")
    )
    a_rad = np.deg2rad(g.loc[valid_aspect, col_aspect].astype("float32"))
    g["northness"] = np.nan
    g["eastness"]  = np.nan
    g.loc[valid_aspect, "northness"] = np.cos(a_rad).astype("float32")
    g.loc[valid_aspect, "eastness"]  = np.sin(a_rad).astype("float32")

    # agg
    def q90(s: pd.Series) -> float:
        return float(s.quantile(0.9)) if len(s) else np.nan

    agg = g.groupby(["__ix", "__iy"]).agg(
        elev_mean=(col_elev, "mean"),
        elev_std =(col_elev, "std"),
        elev_min =(col_elev, "min"),
        elev_max =(col_elev, "max"),
        slope_mean=(col_slope, "mean"),
        slope_std =(col_slope, "std"),
        slope_p90 =(col_slope, q90),
        n_points =(col_elev, "size"),
        north_mean=("northness", "mean"),
        east_mean =("eastness", "mean"),
    ).reset_index()

    # rango de elevacion dem
    agg["elev_range"] = (agg["elev_max"] - agg["elev_min"]).astype("float32")

    # agg promedio
    east = agg.pop("east_mean").astype("float64")
    north = agg.pop("north_mean").astype("float64")
    # mean aspect en [0, 360)
    aspect_mean = (np.degrees(np.arctan2(east, north)) + 360.0) % 360.0
    # R en [0,1]: 1 = todas las orientaciones alineadas
    aspect_R = np.sqrt(east**2 + north**2)
    agg["aspect_mean"] = aspect_mean.astype("float32")
    agg["aspect_R"] = aspect_R.astype("float32")

    # centroide
    cx = (agg["__ix"].to_numpy() + 0.5) * cell_size_m
    cy = (agg["__iy"].to_numpy() + 0.5) * cell_size_m
    geom = gpd.points_from_xy(cx, cy, crs=f"EPSG:{utm_epsg}")

    out = gpd.GeoDataFrame(
        agg.drop(columns=["__ix", "__iy"]),
        geometry=geom,
        crs=f"EPSG:{utm_epsg}"
    ).to_crs(gdf.crs)

    return out



##############################################

## load area del incendio
incendio = 'santa_ana'
path_area = f"data/procesado/areas/{incendio}.geojson" 
gdf = gpd.read_file(path_area)
gdf = gdf.to_crs("EPSG:4326")

## dividimos el area grande en 4 secciones
grilla = crear_grilla(gdf.total_bounds)

tiles = gpd.overlay(grilla, gdf, how="intersection")
tiles.to_file(f"data/dem/tiles_dividido_{incendio}.geojson")
# tiles = gpd.read_file(f"data/dem/tiles_dividido_{incendio}.geojson")



## descarga gee
col = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM")

for i, tile in tiles.iterrows():
    geom = geemap.geopandas_to_ee(gpd.GeoDataFrame([tile], crs="EPSG:4326"))
    
    ## obtener bandas
    terrain_per_tile = col.map(per_img)

    ## recortar geom
    terrain = terrain_per_tile.mosaic().clip(geom)

    # rm valores nan
    img_export = terrain.unmask(-9999).toFloat()

    out_path = f"data/dem/dem_{incendio}_{i}.tif"
    print('guardando info:', out_path)
    geemap.ee_export_image(
        img_export,
        filename=out_path,
        region=geom.geometry(),
        scale=30,
        file_per_band=False
    )

############## to geodataframe

carpeta_tifs = "data/dem"
rutas_tif = glob(os.path.join(carpeta_tifs, "*.tif"))

lista_gdf = []
for path in rutas_tif:
    print('leyendo ruta: ', path)
    gdf = raster_centroids_to_gdf(path)
    print(gdf.head())
    print(gdf.shape)
    lista_gdf.append(gdf)
    
    
    
gdf_final = pd.concat(lista_gdf)
gdf_final = gdf_final[~gdf_final.eval('band1 == 0 & band2==0 & band3 ==0')]


gdf_final = gdf_final.rename(columns = {'band1': 'elevacion',
                                        'band2': 'slope',
                                        'band3': 'aspect'})

gdf_final = gdf_final[~gdf_final.eval('elevacion == -9999 & slope==-9999  & aspect ==-9999')]

gdf_final.loc[gdf_final['elevacion'].between(-5, 0), 'elevacion'] = 0.0  ## valores borde a rio, lagunas o mar pueden ser negativos

for c in ('elevacion', 'slope', 'aspect'):
    gdf_final.loc[gdf_final[c] <= -9999, c] = np.nan


gdf_final.to_file(f'data/procesado/DEM/DEM_{incendio}.geojson')


gdf_375 = aggregate_to_viirs_cells(gdf_final, col_elev='elevacion', cell_size_m=375)
gdf_375.to_file(f'data/procesado/DEM/DEM_{incendio}_375.geojson')

gdf_100 = aggregate_to_viirs_cells(gdf_final, col_elev='elevacion', cell_size_m=100)
gdf_100.to_file(f'data/procesado/DEM/DEM_{incendio}_100.geojson')

gdf_50 = aggregate_to_viirs_cells(gdf_final, col_elev='elevacion', cell_size_m=50)
gdf_50.to_file(f'data/procesado/DEM/DEM_{incendio}_50.geojson')

gdf_50


gdf_375 = gpd.read_file(f'data/procesado/DEM/DEM_{incendio}_375.geojson')


import matplotlib.pyplot as plt
import contextily as cx
# ax = gdf_final[:100000].plot(column="slope", cmap="viridis", markersize=3, alpha=0.9, legend=True)
ax = gdf_100.plot(column="elev_mean", cmap="viridis", markersize=3, alpha=0.9, legend=True)
cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)
ax.set_axis_off()
plt.show()