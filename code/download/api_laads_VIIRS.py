import argparse
import os
import urllib.parse

import geopandas as gpd
import requests
from dotenv import load_dotenv
from shapely.geometry import MultiPolygon, Polygon

from code.download.config import VIIRS_PRODUCTS, get_event



def polygon_to_bbox_format(geom):
    """Convierte un Polygon o MultiPolygon Shapely al formato BBOX de LAADS."""
    if isinstance(geom, Polygon):
        coords = list(geom.exterior.coords)
    elif isinstance(geom, MultiPolygon):
        largest = max(geom.geoms, key=lambda g: g.area)
        coords = list(largest.exterior.coords)

    lons = [pt[0] for pt in coords]
    lats = [pt[1] for pt in coords]

    bbox_str = f"[BBOX]N{max(lats)} S{min(lats)} E{max(lons)} W{min(lons)}"
    bbox_encoded = urllib.parse.quote(bbox_str)
    return bbox_str, bbox_encoded


def download_laads_files_json(products, start_date, end_date, bbox, output_folder, token):
    """Descarga archivos desde LAADS DAAC usando autenticacion con token."""
    
    base_url = "https://ladsweb.modaps.eosdis.nasa.gov/api/v2/content/details/"
    headers = {"Authorization": f"Bearer {token}"}
    page = 1
    os.makedirs(output_folder, exist_ok=True)

    while True:
        params = {
            "products": products,
            "temporalRanges": f"{start_date}..{end_date}",
            "regions": bbox,
            "page": page,
        }

        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error al consultar la API (pag {page}): {response.status_code}")
            print(response.text)
            break

        result = response.json()
        files = result.get("content", [])
        if not files:
            print("No hay mas archivos para descargar.")
            break

        for file_info in files:
            file_url = file_info["downloadsLink"]
            filename = os.path.join(output_folder, os.path.basename(file_url))

            if os.path.exists(filename):
                print(f"El archivo ya existe: {filename}")
                continue

            print(f"Descargando: {file_url}")
            file_response = requests.get(file_url, headers=headers, stream=True)
            if file_response.status_code == 200:
                with open(filename, "wb") as file:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"Guardado: {filename}")
            else:
                print(f"Error al descargar: {file_url} (status {file_response.status_code})")

        page += 1


def get_laads_token() -> str:
    load_dotenv()
    try:
        return os.environ["token"]
    except KeyError as exc:
        raise RuntimeError("Falta la variable 'token' en el archivo .env") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga productos VIIRS desde LAADS DAAC")
    parser.add_argument("--event", default="santa_ana", help="Evento definido en config.py")
    parser.add_argument("--satellite", default="suomi", choices=sorted(VIIRS_PRODUCTS))
    parser.add_argument("--product", default="coords", help="Tipo de producto definida para el satelite")
    parser.add_argument("--output-dir", default=None, help="Carpeta de output opcional")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    event = get_event(args.event)
    products_by_satellite = VIIRS_PRODUCTS[args.satellite]
    try:
        product = products_by_satellite[args.product]
    except KeyError as exc:
        valid = ", ".join(sorted(products_by_satellite))
        raise ValueError(f"Producto desconocido para {args.satellite}: {args.product}. Opciones: {valid}") from exc

    areas = gpd.read_file(event.area_path).to_crs(epsg=4326)
    bbox_str, _ = polygon_to_bbox_format(areas.geometry.iloc[0])
    output_dir = args.output_dir or f"datos-viirs/{args.satellite.upper()}/{event.name}/{args.product.upper()}"

    download_laads_files_json(
        products=product,
        start_date=event.start_iso,
        end_date=event.end_iso,
        bbox=bbox_str,
        output_folder=output_dir,
        token=get_laads_token(),
    )


if __name__ == "__main__":
    main()
