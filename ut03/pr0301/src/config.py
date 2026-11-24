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

# Validación del formato de las credenciales temporales de AWS Academy.
# Un access key ID tiene 20 caracteres, el secret access key 40 y el session
# token es una cadena larga. Si se copian los valores de ejemplo truncados,
# boto3 devuelve errores poco claros (400 Bad Request, InvalidToken, etc.).
errores_credenciales = []

if len(AWS_ACCESS_KEY_ID) != 20:
    errores_credenciales.append(
        "AWS_ACCESS_KEY_ID debe tener 20 caracteres (suele empezar por ASIA o AKIA)."
    )

if len(AWS_SECRET_ACCESS_KEY) != 40:
    errores_credenciales.append(
        "AWS_SECRET_ACCESS_KEY debe tener 40 caracteres."
    )

if len(AWS_SESSION_TOKEN) < 100:
    errores_credenciales.append(
        "AWS_SESSION_TOKEN parece truncado; debe ser una cadena larga."
    )

if errores_credenciales:
    raise ValueError(
        "Las credenciales de AWS no son válidas:\n- "
        + "\n- ".join(errores_credenciales)
        + "\n\nCopia el bloque completo desde AWS Academy -> AWS Details -> Show "
        "y pégalo en el fichero .env (sin el encabezado [default])."
    )
