import os
from pathlib import Path

from dotenv import load_dotenv

# Raíz del proyecto (carpeta pr0301), independientemente del directorio desde
# el que se ejecute el script o el cuaderno.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

# Credenciales AWS
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# S3
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# AEMET
AEMET_API_KEY = os.getenv("AEMET_API_KEY")

# Rutas locales de los catálogos
DATA_DIR = BASE_DIR / "data"
RUTA_MITECO = DATA_DIR / "playas.csv"
RUTA_AEMET = DATA_DIR / "playas_codigos.csv"

# Validación: si falta alguna variable crítica, el programa para
variables_criticas = {
    "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
    "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
    "AWS_SESSION_TOKEN": AWS_SESSION_TOKEN,
    "S3_BUCKET_NAME": S3_BUCKET_NAME,
    "AEMET_API_KEY": AEMET_API_KEY,
}

for nombre, valor in variables_criticas.items():
    if not valor:
        raise ValueError(f"Falta la variable de entorno crítica: {nombre}")
