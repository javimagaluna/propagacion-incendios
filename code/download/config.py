from dataclasses import dataclass
from datetime import date
from pathlib import Path


GEE_PROJECT = "tesis-incendios"

## paths ----------------------------------------------------------------------
DATA_DIR = Path("data")
PROCESSED_DIR = DATA_DIR / "procesado"
AREAS_DIR = PROCESSED_DIR / "areas"
DEM_DIR = PROCESSED_DIR / "DEM"
ERA5_DIR = PROCESSED_DIR / "era5"
NDVI_DIR = DATA_DIR / "NDVI"
HEALPIX_GRID_PATH = PROCESSED_DIR / "grilla" / "areas_grilla_healpix.geojson"
SATELLITE_UNION_DIR = PROCESSED_DIR / "satellite_data" / "union"

## class dates ----------------------------------------------------------------
@dataclass(frozen=True)
class FireEvent:
    name: str
    area_path: Path
    start_date: date
    end_date: date

    @property
    def start_iso(self) -> str:
        return self.start_date.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end_date.isoformat()

## events configuration: fire, path and date c: ------------------------------

EVENTS = {
    "las_maquinas": FireEvent(
        name="las_maquinas",
        area_path=AREAS_DIR / "las_maquinas.geojson",
        start_date=date(2017, 1, 15),
        end_date=date(2017, 2, 5),
    ),
    "santa_ana": FireEvent(
        name="santa_ana",
        area_path=AREAS_DIR / "santa_ana_2023.geojson",
        start_date=date(2023, 1, 29),
        end_date=date(2023, 3, 6),
    ),
}

def get_event(name: str) -> FireEvent:
    try:
        return EVENTS[name]
    except KeyError as exc:
        valid = ", ".join(sorted(EVENTS))
        raise ValueError(f"Evento desconocido: {name}. Opciones: {valid}") from exc


## names of satellite products -----------------------------------------------

VIIRS_PRODUCTS = {
    "suomi": {
        "bandas": "VNP02IMG",
        "coords": "VNP03IMG",
        "active_fire": "VNP14IMG",
    },
    "noaa1": {
        "bandas": "VJ102IMG",
        "coords": "VJ103IMG",
    },
    "noaa2": {
        "bandas": "VJ202IMG",
        "coords": "VJ203IMG",
    },
}

ERA5_VARIABLES = [
    "dewpoint_temperature_2m",
    "temperature_2m",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
]


