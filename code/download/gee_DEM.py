import ee
import geemap
import geopandas as gpd

ee.Authenticate()  
ee.Initialize(project='tesis-incendios')


# area 
gdf = gpd.read_file("data/procesado/grilla/areas_grilla_healpix.geojson")
gdf['id_num'] = gdf['Codigo'].astype('category').cat.codes
gdf.to_file("data/procesado/grilla/areas_grilla_healpix_id_num.geojson")

zonas = gdf['zona'].unique()

for z in zonas:
    print(f"Procesando zona: {z}")

    # Filtrar celdas
    gdf_z = gdf[gdf['zona'] == z]
    
    fc = geemap.geopandas_to_ee(gdf_z)
    id_image = fc.reduceToImage(properties=['id_num'], reducer=ee.Reducer.first())

    # Cargar DEM
    collection = ee.ImageCollection("COPERNICUS/DEM/GLO30").filterBounds(fc)
    raw_dem = collection.first().clip(fc)
    dem = raw_dem.select("DEM")
    edm = raw_dem.select("EDM")
    mask = edm.gt(0)
    dem_masked = dem.updateMask(mask)

    # pendiente y orientación
    terrain = ee.Terrain.products(dem_masked)
    slope = terrain.select("slope")
    aspect = terrain.select("aspect")

    # Exportar DEM
    ee.batch.Export.image.toDrive(
        image=dem_masked,
        description=f"DEM_{z}",
        folder='GEE_exports',
        region=fc.geometry(),
        scale=30,
        fileFormat='GeoTIFF',
        maxPixels=1e9
    ).start()

    # Exportar pendiente
    ee.batch.Export.image.toDrive(
        image=slope,
        description=f"Slope_{z}",
        folder='GEE_exports',
        region=fc.geometry(),
        scale=30,
        fileFormat='GeoTIFF',
        maxPixels=1e9
    ).start()

    # Exportar orientación
    ee.batch.Export.image.toDrive(
        image=aspect,
        description=f"Aspect_{z}",
        folder='GEE_exports',
        region=fc.geometry(),
        scale=30,
        fileFormat='GeoTIFF',
        maxPixels=1e9
    ).start()

    # id por celda
    ee.batch.Export.image.toDrive(
        image=id_image,
        description=f"ID_{z}",
        folder='GEE_exports',
        region=fc.geometry(),
        scale=30,
        fileFormat='GeoTIFF',
        maxPixels=1e9
    ).start()

# print(export_dem.status())
# print(export_slope.status())

#### PLOT ---------------------------------------
# import rasterio
# import matplotlib.pyplot as plt

# # Abrir el archivo
# with rasterio.open("data/procesado/DEM/DEM_bee_rock_creek.tif") as src:
#     dem = src.read(1)  # leer la primera banda
#     profile = src.profile  # metadatos (CRS, resolución, etc.)

# # Mostrar como imagen
# plt.imshow(dem, cmap="terrain")
# plt.colorbar(label="Elevación (m)")
# plt.title("DEM Zona 1")
# plt.show()