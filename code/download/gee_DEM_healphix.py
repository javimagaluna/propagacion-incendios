import ee
import geemap
import geopandas as gpd


ee.Authenticate()  
ee.Initialize(project='tesis-incendios')

#####################################################################################

#### functions

def process_image_cells(image, fc):
    """
    Returns satellite image reduced to rhealpix grid cells in a feature collection.

    Parameters
    ----------
    image: ee.Image
        GEE image containing satellite data.
    fc: ee.FeatureCollection
        GEE feature collection containing rhealpix grid cells.
    """

    scale_reprojection = 30. # used scale from docs
    # image_reprojected = image.reproject(crs="EPSG:4326", scale=scale_reprojection)

    fc_reduced = image.reduceRegions(
        collection = fc,
        reducer = ee.Reducer.mean(),
        scale = scale_reprojection
    )

    df = geemap.ee_to_df(fc_reduced)

    return df


#####################################################################################

# area 
gdf = gpd.read_file("data/procesado/grilla/areas_grilla_healpix.geojson")

zonas = gdf['zona'].unique()

for z in zonas:
    print(f"Procesando zona: {z}")

    # Filtrar celdas de la zona
    gdf_z = gdf[gdf['zona'] == z]
    fc = geemap.geopandas_to_ee(gdf_z)

    # ---------- DEM ----------
    dem_image = ee.ImageCollection("COPERNICUS/DEM/GLO30").filterBounds(fc).first().select("DEM")
    print(f"Reduciendo DEM ...")
    df_dem = process_image_cells(dem_image, fc)
    df_dem = df_dem.rename(columns = {'mean':'dem'})
    
    # ---------- Slope ----------
    terrain = ee.Terrain.products(dem_image)
    slope_image = terrain.select("slope")
    print(f"Reduciendo pendiente ...")
    df_slope = process_image_cells(slope_image, fc)
    df_slope = df_slope.rename(columns = {'mean':'slope'})
    
    # ---------- Aspect ----------
    aspect_image = terrain.select("aspect")
    print(f"Reduciendo orientación...")
    df_aspect = process_image_cells(aspect_image, fc)
    df_aspect = df_aspect.rename(columns = {'mean':'aspect'})

    df_merge = df_dem.merge(df_slope,
                            on=['Codigo', 'zona'],
                            how="inner").merge(
                                df_aspect,
                                on=['Codigo', 'zona'],
                                how="inner"
                                )
    
    gdf_z = gdf_z.merge(df_merge, on=['Codigo', 'zona'], how = 'left')
    print(gdf_z.head())
    gdf_z.to_file(f'data/procesado/DEM/dem_{z}.geojson')
    


#### PLOT ---------------------------------------

# import matplotlib.pyplot as plt

# # DEM
# gdf_z.plot(column="dem", cmap="terrain", legend=True, figsize=(8, 6))
# plt.title("Elevación (DEM)")
# plt.show()

# # Slope
# gdf_z.plot(column="slope", cmap="viridis", legend=True, figsize=(8, 6))
# plt.title("Pendiente (°)")
# plt.show()

# # Aspect
# gdf_z.plot(column="aspect", cmap="twilight", legend=True, figsize=(8, 6))
# plt.title("Orientación de la pendiente (°)")
# plt.show()
