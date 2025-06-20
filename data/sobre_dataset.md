### Descripción del conjunto de datos

El conjunto de datos está conformado por información de sensores satelitales y modelos ambientales, relevantes para el análisis de fenómenos térmicos y condiciones del entorno terrestre. Cada observación corresponde a una ubicación geográfica específica e incluye variables térmicas, topográficas y meteorológicas.

La información térmica se obtiene a partir del sensor VIIRS (Visible Infrared Imaging Radiometer Suite) a bordo de los satélites Suomi NPP, NOAA-20 (J1) y NOAA-21 (J2), mientras que la topografía se deriva del modelo Copernicus DEM GLO-30, y las condiciones meteorológicas provienen de productos de reanálisis atmosférico (ERA5, ECMWF Climate Reanalysis).

Las resoluciones espaciales y frecuencia temporal asociadas a cada producto corresponden a:

- Bandas VIIRS: Resolución espacial de 375 metros con frecuencia de observación de 12 hrs aprox.
- Topografía: Resolución espacial de 30 metros, sin variación temporal (modelo de elevación fijo).
- Meteorológica: Resolución espacial de 9 km aprox con frecuencia de observación horaria

Las variables disponibles se describen a continuación:

| Categoría  | Variable | Producto  |  Descripción  |
| ---------------- | ---------------- | ---------------- | ---------------- |
| **VIIRS NPP/J1/J2**| Banda I04 (3.74 $\mu$m)| VNP02IMG, VJ102IMG, VJ202IMG | Radiancia de infrarrojos de onda media, utilizada para detectar fuentes térmicas activas como incendios, flujos de lava o emisiones industriales. Alta sensibilidad a temperaturas elevadas. |
|                | Banda I05 (11.45 $\mu$m)| VNP02IMG, VJ102IMG, VJ202IMG | Radiancia de infrarrojos de onda larga, empleada para estimar la temperatura de la superficie terrestre y analizar la energía térmica emitida por el suelo y la vegetación.  |
| **Topográfica**      | DEM    | DEM/GLO30    | Modelo Digital de Elevación que representa la altitud del terreno sobre el nivel del mar, expresada en metros. Basado en datos radar de alta precisión. 
|                     | slope     | DEM/GLO30   | Derivada de DEM, pendiente del terreno calculada como la tasa de cambio de la elevación entre píxeles adyacentes. Expresada en grados.   |
|                     | aspect     | DEM/GLO30  | Derivada de DEM, dirección hacia la cual se orienta la pendiente, en grados desde el norte geográfico (0° a 360°). |
| **Meteorológica**    | u10   | ERA5-Land Hourly| Componente de viento este-oeste a 10 metros sobre el suelo. Positivos hacia el este. Se combina con v10 para estimar la velocidad del viento. |
|                     | v10   | ERA5-Land Hourly | Componente de viento norte-sur a 10 metros sobre el suelo. Positivos hacia el norte. Se combina con u10 para estimar la velocidad del viento.  |
|             | 2m temperature | ERA5-Land Hourly| Temperatura del aire a 2 metros sobre la superficie, en grados Celsius. Refleja las condiciones térmicas del entorno inmediato y nos permite estimar la humedad relativa.  |
|                 | 2m dewpoint temperature | ERA5-Land Hourly | Temperatura de rocío a 2 metros, en Kelvin. Junto a la temperatura *2m temperature* permite estimar la humedad relativa. |



Para integrar las variables con diferentes resoluciones espaciales, se utilizó una grilla basada en el sistema rHEALPix (Hierarchical Equal Area isoLatitude Pixelation). Esta grilla permite proyectar todos los datos sobre una estructura espacial homogénea, conservando áreas iguales por celda y facilitando el análisis conjunto entre variables térmicas, topográficas y meteorológicas. Para este estudio, se emplea una grilla de nivel 10, correspondiente a una resolución aproximada de 156 metros.