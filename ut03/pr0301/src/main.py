import logging
import pandas as pd
from datetime import datetime, timezone

from config import (
    S3_BUCKET_NAME,
    AEMET_API_KEY,
)
from s3_manager import subir_fichero_local, subir_json_memoria
from aemet_client import obtener_prediccion

# ─── Configuración del logger ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ─── Constantes ─────────────────────────────────────────────────────────────
PROVINCIA_ELEGIDA = "Alicante"   # Cambia por cualquier provincia costera
MAX_PLAYAS = 15
RUTA_MITECO = "./data/playas.csv"
RUTA_AEMET  = "./data/playas_codigos.csv"


def main():
    logging.info("=== Iniciando pipeline de ingesta hacia Capa Bronce ===")
    archivos_subidos = 0

    # ── 1. Subir los dos CSV a S3 ────────────────────────────────────────────
    logging.info("Subiendo catálogo MITECO a S3...")
    subir_fichero_local(
        ruta_local=RUTA_MITECO,
        bucket=S3_BUCKET_NAME,
        s3_key="bronce/catalogos/miteco_playas/v1/playas.csv",
        source="MITECO_OpenData"
    )
    archivos_subidos += 1

    logging.info("Subiendo catálogo AEMET a S3...")
    subir_fichero_local(
        ruta_local=RUTA_AEMET,
        bucket=S3_BUCKET_NAME,
        s3_key="bronce/catalogos/aemet_codigos/v1/playas_codigos.csv",
        source="AEMET_Catalogo"
    )
    archivos_subidos += 1

    # ── 2. Leer playas.csv y filtrar provincia costera ───────────────────────
    logging.info(f"Filtrando playas de la provincia: {PROVINCIA_ELEGIDA}...")
    df_miteco = pd.read_csv(RUTA_MITECO, sep=",", encoding="utf-8", dtype={"Código_IN": str})
    df_miteco["Código_IN"] = df_miteco["Código_IN"].str.zfill(5)

    df_provincia = df_miteco[df_miteco["Provincia"].str.contains(PROVINCIA_ELEGIDA, case=False, na=False)]
    codigos_ine = df_provincia["Código_IN"].unique().tolist()
    logging.info(f"Municipios encontrados en {PROVINCIA_ELEGIDA}: {len(codigos_ine)}")

    # ── 3. Filtrar playas_codigos.csv por municipios de la provincia ─────────
    logging.info("Cruzando con catálogo AEMET por código INE...")
    df_aemet = pd.read_csv(RUTA_AEMET, sep=";", encoding="ISO-8859-1", dtype={"ID_PLAYA": str, "ID_MUNICIPIO": str})
    df_aemet["ID_MUNICIPIO"] = df_aemet["ID_MUNICIPIO"].str.zfill(5)

    df_filtrado = df_aemet[df_aemet["ID_MUNICIPIO"].isin(codigos_ine)]
    ids_playa = df_filtrado["ID_PLAYA"].unique().tolist()[:MAX_PLAYAS]
    logging.info(f"Playas AEMET encontradas (máx {MAX_PLAYAS}): {len(ids_playa)}")

    # ── 4. Descargar predicciones y subir a S3 ───────────────────────────────
    ahora = datetime.now(timezone.utc)
    ruta_particion = f"year={ahora.year}/month={ahora.month:02d}/day={ahora.day:02d}"

    for id_playa in ids_playa:
        logging.info(f"Descargando predicción para playa {id_playa}...")
        datos = obtener_prediccion(id_playa, AEMET_API_KEY)

        if datos is None:
            logging.warning(f"Sin datos para playa {id_playa}. Saltando...")
            continue

        s3_key = (
            f"bronce/meteorologia/aemet_prediccion_playas/"
            f"{ruta_particion}/"
            f"pred_playa_{id_playa}_{ahora.strftime('%H%M%S')}.json"
        )
        subir_json_memoria(datos, S3_BUCKET_NAME, s3_key)
        archivos_subidos += 1

    # ── 5. Resumen final ─────────────────────────────────────────────────────
    logging.info("=== Pipeline finalizado ===")
    logging.info(f"Total de archivos subidos a S3: {archivos_subidos}")


if __name__ == "__main__":
    main()