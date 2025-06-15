import ee
import geemap


ee.Authenticate()  
ee.Initialize(project='tesis-incendios')


# area 
aoi = ee.Geometry.Rectangle([-73, -39, -71.5, -37.5])

## cargando imagen
collection = ee.ImageCollection("COPERNICUS/DEM/GLO30").filterBounds(aoi)
raw_dem = collection.first().clip(aoi)

## banda DEM
dem = raw_dem.select('DEM')
edm = raw_dem.select('EDM')
mask = edm.gt(0)
dem_masked = dem.updateMask(mask)

## calculo pendiente y orientacion
terrain = ee.Terrain.products(dem_masked)
slope = terrain.select('slope')
aspect = terrain.select('aspect')

task = geemap.download_ee_image(
    image=dem_masked,
    description='Copernicus_DEM_30m',
    folder='GEE_exports',
    region=aoi,
    scale=30,
    fileFormat='GeoTIFF'
)

task.start()