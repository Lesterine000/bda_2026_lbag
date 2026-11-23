import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_DEFAULT_REGION,
    AWS_SECRET_ACCESS_KEY,
    AWS_SESSION_TOKEN,
)

# Reglas básicas de nombres de bucket de S3
PATRON_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")

s3_client = boto3.client(
    "s3",
    region_name=AWS_DEFAULT_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
)


def _timestamp_utc():
    """Devuelve la fecha y hora actual en UTC con formato ISO 8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _metadata(source):
    """Construye los metadatos nativos de trazabilidad que se adjuntan a cada objeto."""
    return {
        "source": source,
        "ingestion_timestamp": _timestamp_utc(),
    }


def crear_bucket_si_no_existe(bucket, region=None):
    """Crea el bucket si no existe y devuelve True si lo ha creado.

    Si el bucket ya existe no hace nada. Se lanza una excepción si el nombre
    no es válido o si existe en otra cuenta y no tenemos permisos.
    """
    region = region or AWS_DEFAULT_REGION

    if not PATRON_BUCKET.match(bucket):
        raise ValueError(
            f"Nombre de bucket no válido: '{bucket}'. Debe tener entre 3 y 63 "
            "caracteres, estar en minúsculas y empezar/terminar por letra o número."
        )

    try:
        s3_client.head_bucket(Bucket=bucket)
        logging.info(f"El bucket ya existe: s3://{bucket}")
        return False
    except ClientError as error:
        codigo = error.response.get("Error", {}).get("Code", "")

        # El bucket no existe: lo creamos
        if codigo in ("404", "NoSuchBucket", "NotFound"):
            argumentos = {"Bucket": bucket}
            if region != "us-east-1":
                argumentos["CreateBucketConfiguration"] = {
                    "LocationConstraint": region
                }

            s3_client.create_bucket(**argumentos)
            logging.info(f"Bucket creado: s3://{bucket} (región {region})")
            return True

        # El bucket existe en otra región: no es necesario recrearlo
        if codigo in ("301", "PermanentRedirect"):
            logging.warning(
                f"El bucket {bucket} existe en otra región; se usará tal cual."
            )
            return False

        # El bucket existe, pero pertenece a otra cuenta
        if codigo in ("403", "AccessDenied"):
            raise PermissionError(
                f"El bucket '{bucket}' existe pero no tienes permisos sobre él. "
                "Elige otro nombre en S3_BUCKET_NAME."
            ) from error

        raise


def subir_fichero_local(ruta_local, bucket, s3_key, source, content_type=None):
    """Sube un fichero desde disco local a S3 con metadatos de trazabilidad."""
    ruta = Path(ruta_local)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el fichero local: {ruta}")

    extra_args = {"Metadata": _metadata(source)}
    if content_type:
        extra_args["ContentType"] = content_type

    try:
        s3_client.upload_file(
            Filename=str(ruta),
            Bucket=bucket,
            Key=s3_key,
            ExtraArgs=extra_args,
        )
        logging.info(f"Fichero subido correctamente: s3://{bucket}/{s3_key}")
        return s3_key
    except Exception as error:
        logging.error(f"Error al subir {ruta}: {error}")
        raise


def subir_json_memoria(datos_json, bucket, s3_key, source="AEMET_API"):
    """Sube un JSON directamente desde memoria RAM a S3 con metadatos."""
    if datos_json is None:
        raise ValueError("No se pueden subir datos JSON nulos a S3.")

    try:
        json_en_bytes = json.dumps(
            datos_json, ensure_ascii=False, indent=2
        ).encode("utf-8")

        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json_en_bytes,
            ContentType="application/json",
            Metadata=_metadata(source),
        )
        logging.info(f"JSON subido desde memoria: s3://{bucket}/{s3_key}")
        return s3_key
    except Exception as error:
        logging.error(f"Error al subir JSON a {s3_key}: {error}")
        raise
