# Descarga de datos satelitales

Scripts de descarga de datos satelitales, info DEM y climática

## Scripts de descargas

- `api_laads_VIIRS.py`: descarga archivos VIIRS desde LAADS.
- `gee_NDVI_16days.py`: descarga puntos NDVI VIIRS cada 16 dias.
- `gee_DEM_area.py`: descarga DEM por area y agrega a celdas regulares.
- `gee_era5_grilla_km.py`: descarga ERA5 sobre puntos de grilla regular.
- `healpix/gee_era5_healpix.py`: descarga ERA5 y lo pondera hacia celdas HealPix (no usado).
- `healpix/gee_DEM_healpix.py`: reduce DEM, slope y aspect sobre la grilla HealPix (no usado).

## Scripts de configuración y helpers

- `config.py`: eventos, fechas, rutas y productos satelitales.
- `gee_utils.py`: inicio de sesion en Google Earth Engine y helpers de areas.

## Nombre de los eventos descargados

- `las_maquinas`: 2017-01-15 a 2017-02-05
- `santa_ana`: 2023-01-29 a 2023-03-06

Ejemplo de descarga de datos c:

```powershell
python code/download/api_laads_VIIRS.py --event santa_ana --satellite suomi --product coords
python code/download/gee_NDVI_16days.py --event las_maquinas
python code/download/gee_DEM_area.py --event santa_ana
python code/download/gee_era5_grilla_km.py --event santa_ana --satellite suomi
```
