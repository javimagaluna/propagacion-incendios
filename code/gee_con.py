import ee
import geemap


ee.Authenticate()  # Solo la primera vez
ee.Initialize(project='tesis-incendios')


# area chile
chile = ee.Geometry.BBox(-75, -56, -66, -17)

# VIIRS (detección de fuego)
viirs = ee.ImageCollection('NASA/LANCE/NOAA20_VIIRS/C2') \
    .filterBounds(chile) \
    .filterDate('2025-02-01', '2025-02-03') \
    .first()  # solo una imagen para el ejemplo

viirs.getInfo()  

viirs.bandNames().getInfo() 

viirs.select('acq_time').getInfo()

img_list = viirs.toList(viirs.size())

viirs.date().format('YYYY-MM-dd HH:mm:ss').getInfo()