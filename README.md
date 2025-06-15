# propagacion-incendios

### Descripción

Este proyecto tiene como objetivo modelar la propagación de incendios forestales utilizando datos satelitales, principalmente del sensor VIIRS (bandas térmicas I4 e I5), junto con información topográfica y climática...

### Estructura del repositorio

```text
data/              # Datos brutos y procesados (uso interno)
notebooks/         # Notebooks con Viz y pruebas
code/              # Scripts
└─ download/            # Conexiones para descargar archivos
└─ procesamiento/       # procesamiento de bases brutas
└─ modelamiento/        # proximamente
```


#### Sobre algunos scripts

- `code/download/descarga_api.py`: Código de conexión y descarga de datos satelitales de VIIRS. Para realizar descargas es necesario registrarse en la pág de LAADS y generar un token. Para mayor info, revisar [link](https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/api-v2/quick-start-guide/)
- `code/download/gee_DEM.py`: Código de descarga de datos satelitales DEM GLO30 desde Google Earth Engine. 
- `code/procesamiento/procesamiento_nc.py`: Los archivos recolectados de LAADS provienen en formato .nc, en donde tenemos en un archivo las bandas y en otro la geolocalización de los datos, por lo que se generó un código que uniera los archivos para las zonas de interes. Esta unión de archivos calcula 
- `code/procesamiento/grilla_healpix.py`: Genera grilla HealPix para cada área. Cada celda posee una resolución nivel 10 (156m). Esto se usa para tener una zona fija de observación, pues en cada pasada del satélite no obtenemos los mismos centroides (hay un leve desplazamiento).
- `notebooks/puntao_de_calor.ipynb`: Visualización de centroides de anomalías térmicas desde FIRMS para áreas de EEUU. 



### Sobre los datos 🛰️

| Nombre del Producto | Satélite / Sensor| Descripción | Resolución Espacial / Temporal | Link |
|---|---|---|---|---|
| FIRMS (Focos activos) | Suomi, NOAA-20, NOAA-21 / VIIRS | Detección de focos activos de incendio basada en emisión térmica.| ~375 m / NRT|[Link](https://firms.modaps.eosdis.nasa.gov/download/)|
| VNP02IMG | Suomi NPP / VIIRS | Imágenes en bruto (Level 1) de bandas térmicas (I4 e I5)| 375 m / Dos veces al día (aprox.)|[Link](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP02IMG)|
| VJ102IMG| NOAA-20 (JPSS-1) / VIIRS | Equivalente a VNP02IMG pero del satélite NOAA-20 | 375 m / Dos veces al día (aprox.)|[Link](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VJ102IMG)|
| VJ202IMG| NOAA-21 (JPSS-2) / VIIRS | Equivalente a VNP02IMG pero del satélite NOAA-21 | 375 m / Dos veces al día (aprox.)|[Link](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VJ202IMG)|
| VNP03IMG | Suomi NPP / VIIRS | Geolocalización VNP02IMG| 375 m / Dos veces al día (aprox.)|[Link](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP03IMG)|
| VJ103IMG| NOAA-20 (JPSS-1) / VIIRS | Geolocalización VJ103IMG| 375 m / Dos veces al día (aprox.)|[Link](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VJ103IMG)|
| VJ203IMG| NOAA-21 (JPSS-2) / VIIRS | Geolocalización VJ203IMG| 375 m / Dos veces al día (aprox.)|[Link](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VJ203IMG)|
| DEM GLO30| Copernicus |Modelo digital de elevación global| ~30 m / - |[Link](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30?hl=es-419)|
| ERA5| ECMWF| Reanálisis climático con variables de temperatura, humedad, viento, etc.  | ~ km / Horaria |[Link](https://cds.climate.copernicus.eu/)|

