import requests
from dotenv import load_dotenv
import os

from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import urllib.parse

#####################################

def polygon_to_bbox_format(geom):
    """
    Convierte un objeto Shapely Polygon o MultiPolygon en formato [BBOX]N... S... E... W...
    """
    if isinstance(geom, Polygon):
        coords = list(geom.exterior.coords)
    elif isinstance(geom, MultiPolygon):
        # Usamos solo el poligono más grande
        largest = max(geom.geoms, key=lambda g: g.area)
        coords = list(largest.exterior.coords)
    else:
        raise ValueError("El objeto debe ser un Polygon o MultiPolygon de Shapely")

    # Extraer latitudes y longitudes
    lons = [pt[0] for pt in coords]
    lats = [pt[1] for pt in coords]

    # Calcular extremos
    lat_s = min(lats)
    lat_n = max(lats)
    lon_w = min(lons)
    lon_e = max(lons)

    # Formato LAADS DAAC
    bbox_str = f"[BBOX]N{lat_n} S{lat_s} E{lon_e} W{lon_w}"
    bbox_encoded = urllib.parse.quote(bbox_str)

    return bbox_str, bbox_encoded


def download_laads_files_json(products, start_date, end_date, bbox, output_folder, token):
    """
    Descarga archivos desde la API de LAADS DAAC usando autenticación con token.
    
    Parametros:
        products (str): Producto, por ejemplo "VNP14IMG".
        start_date (str): Fecha de inicio en formato "YYYY-MM-DD".
        end_date (str): Fecha de término en formato "YYYY-MM-DD".
        bbox (str): Bounding box en formato "-75,-35,-72,-33".
        output_folder (str): Carpeta donde guardar los archivos descargados.
        token (str): Token de autenticación de LAADS DAAC
    """
    
    base_url = "https://ladsweb.modaps.eosdis.nasa.gov/api/v2/content/details/"
    headers = {"Authorization": f"Bearer {token}"}   ## autenticacion
    page = 1
    os.makedirs(output_folder, exist_ok=True)

    while True:
        params = {
            "products": products,
            "temporalRanges": f"{start_date}..{end_date}",
            "regions": bbox,
            "page": page
        }
        
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"⚠️ Error al consultar la API (página {page}): {response.status_code}")
            print(response.text)
            break

        result = response.json()
        files = result.get("content", [])
        if not files:
            print("No hay mas archivos para descargar.")
            break

        for file in files:
            file_url = file['downloadsLink']
            filename = os.path.join(output_folder, os.path.basename(file_url))

            if os.path.exists(filename):
                print(f"El archivo ya existe: {filename}")
                continue

            # Descargar el archivo
            print(f"⬇️ Descargando: {file_url}")
            file_response = requests.get(file_url, headers=headers, stream=True)
            if file_response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Guardado: {filename}")
            else:
                print(f"❌ Error al descargar: {file_url} (status {file_response.status_code})")

        page += 1



#####################################################
## token de pag
load_dotenv() 
password = os.environ['token']

## areas de interes
path_areas = Path('data/procesado/zonas_incendios/areas_buffer.geojson')
areas = gpd.read_file(path_areas)
geom = areas[areas['zona'] == 'haoe_lead']['geometry'].iloc[0]

bbox_str, _ = polygon_to_bbox_format(geom)


set = ['VNP02IMG', 'VNP03IMG', 'VJ102IMG', 'VJ103IMG', 'VJ202IMG', 'VJ203IMG']
save = ['BANDAS', 'COORDS'] 
satelite = 'NOAA'

if __name__ == "__main__":
    products = set[3]
    start_date = "2025-04-12"
    end_date = "2025-04-22"
    bbox = bbox_str # "[BBOX]N35.8419 S35.77783 E-82.07657 W-82.16226"
    output_dir = f'datos-viirs/{satelite}/{save[1]}'
    token = password

    download_laads_files_json(products, start_date, end_date, bbox, output_dir, token)

