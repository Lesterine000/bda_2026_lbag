import boto3
import logging
from datetime import datetime, timezone

s3_client = boto3.client("s3")

def subir_fichero_local(ruta_local, bucket, s3_key, source):
    """Sube un fichero desde disco local a S3 con metadatos de trazabilidad."""
    timestamp_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    try:
        s3_client.upload_file(
            Filename=ruta_local,
            Bucket=bucket,
            Key=s3_key,
            ExtraArgs={
                "Metadata": {
                    "source": source,
                    "ingestion_timestamp": timestamp_iso
                }
            }
        )
        logging.info(f"Fichero subido correctamente: {s3_key}")
    except Exception as e:
        logging.error(f"Error al subir {ruta_local}: {e}")
        raise


def subir_json_memoria(datos_json, bucket, s3_key):
    """Sube un JSON directamente desde memoria RAM a S3 con metadatos de trazabilidad."""
    import json
    timestamp_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        json_en_bytes = json.dumps(datos_json, ensure_ascii=False, indent=2).encode("utf-8")
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json_en_bytes,
            ContentType="application/json",
            Metadata={
                "source": "AEMET_API",
                "ingestion_timestamp": timestamp_iso
            }
        )
        logging.info(f"JSON subido desde memoria: {s3_key}")
    except Exception as e:
        logging.error(f"Error al subir JSON a {s3_key}: {e}")
        raise