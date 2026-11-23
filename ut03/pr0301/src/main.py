import logging
from datetime import datetime, timezone

import pandas as pd

from config import (
    AEMET_API_KEY,
    RUTA_AEMET,
    RUTA_MITECO,
    S3_BUCKET_NAME,
)
from s3_manager import (
    crear_bucket_si_no_existe,
    subir_fichero_local,
    subir_json_memoria,
)
from aemet_client import obtener_prediccion

# ─── Configuración del logger ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ─── Constantes ─────────────────────────────────────────────────────────────
PROVINCIA_ELEGIDA = "Alicante"  # Cambia por cualquier provincia costera
MAX_PLAYAS = 15

RUTA_S3_MITECO = "bronce/catalogos/miteco_playas/v1/playas.csv"
RUTA_S3_AEMET = "bronce/catalogos/aemet_codigos/v1/playas_codigos.csv"
PREFIJO_PREDICCIONES = "bronce/meteorologia/aemet_prediccion_playas"


def cargar_catalogo_miteco():
    """Lee playas.csv y normaliza el código INE a 5 dígitos."""
    df = pd.read_csv(
        RUTA_MITECO,
        sep=",",
        encoding="utf-8-sig",  # el fichero incluye BOM UTF-8
        dtype={"Código_IN": str},
    )
    df = df.dropna(subset=["Código_IN", "Provincia"]).copy()
    df["Código_IN"] = df["Código_IN"].str.strip().str.zfill(5)
    return df


def obtener_codigos_ine(df_miteco, provincia):
    """Devuelve los códigos INE únicos de los municipios de una provincia."""
    df_provincia = df_miteco[
        df_miteco["Provincia"].str.contains(
            provincia, case=False, na=False, regex=False
        )
    ]
    return sorted(df_provincia["Código_IN"].unique().tolist())


def cargar_catalogo_aemet():
    """Lee playas_codigos.csv (latin1) y normaliza sus códigos."""
    df = pd.read_csv(
        RUTA_AEMET,
        sep=";",
        encoding="ISO-8859-1",
        dtype=str,
    )
    df = df.dropna(subset=["ID_MUNICIPIO", "ID_PLAYA"]).copy()
    df["ID_MUNICIPIO"] = df["ID_MUNICIPIO"].str.strip().str.zfill(5)
    df["ID_PLAYA"] = df["ID_PLAYA"].str.strip().str.zfill(7)
    return df


def seleccionar_playas(df_aemet, codigos_ine, max_playas=MAX_PLAYAS):
    """Cruza ambos catálogos por código INE y devuelve como máximo `max_playas`."""
    df_filtrado = df_aemet[df_aemet["ID_MUNICIPIO"].isin(codigos_ine)]
    df_filtrado = df_filtrado.drop_duplicates(subset=["ID_PLAYA"])
    return df_filtrado.head(max_playas)


def subir_catalogos():
    """Sube los dos catálogos maestros a sus rutas versionadas v1/."""
    logging.info("Subiendo catálogo MITECO a S3...")
    subir_fichero_local(
        ruta_local=RUTA_MITECO,
        bucket=S3_BUCKET_NAME,
        s3_key=RUTA_S3_MITECO,
        source="MITECO_OpenData",
        content_type="text/csv",
    )

    logging.info("Subiendo catálogo AEMET a S3...")
    subir_fichero_local(
        ruta_local=RUTA_AEMET,
        bucket=S3_BUCKET_NAME,
        s3_key=RUTA_S3_AEMET,
        source="AEMET_Catalogo",
        content_type="text/csv",
    )


def main():
    logging.info("=== Iniciando pipeline de ingesta hacia Capa Bronce ===")

    # ── 0. Crear el bucket si no existe ──────────────────────────────────────
    crear_bucket_si_no_existe(S3_BUCKET_NAME)

    archivos_subidos = 0
    playas_omitidas = 0
    errores_subida = 0

    # ── 1. Subir los dos CSV a S3 ────────────────────────────────────────────
    subir_catalogos()
    archivos_subidos += 2

    # ── 2. Leer playas.csv y filtrar provincia costera ───────────────────────
    logging.info(f"Filtrando playas de la provincia: {PROVINCIA_ELEGIDA}...")
    df_miteco = cargar_catalogo_miteco()
    codigos_ine = obtener_codigos_ine(df_miteco, PROVINCIA_ELEGIDA)
    logging.info(
        f"Municipios encontrados en {PROVINCIA_ELEGIDA}: {len(codigos_ine)}"
    )

    if not codigos_ine:
        logging.error(
            f"No se ha encontrado ningún municipio para '{PROVINCIA_ELEGIDA}'. "
            "Revisa el nombre de la provincia."
        )
        return

    # ── 3. Filtrar playas_codigos.csv por municipios de la provincia ─────────
    logging.info("Cruzando con catálogo AEMET por código INE...")
    df_aemet = cargar_catalogo_aemet()
    df_playas = seleccionar_playas(df_aemet, codigos_ine)
    ids_playa = df_playas["ID_PLAYA"].tolist()
    logging.info(
        f"Playas AEMET encontradas (máx. {MAX_PLAYAS}): {len(ids_playa)}"
    )

    if not ids_playa:
        logging.warning(
            "No hay playas de AEMET para los municipios seleccionados. "
            "No se descargará ninguna predicción."
        )

    # ── 4. Descargar predicciones y subirlas a S3 ────────────────────────────
    for id_playa in ids_playa:
        nombre = df_playas.loc[
            df_playas["ID_PLAYA"] == id_playa, "NOMBRE_PLAYA"
        ].iloc[0]
        logging.info(f"Descargando predicción de '{nombre}' ({id_playa})...")

        datos = obtener_prediccion(id_playa, AEMET_API_KEY)
        if datos is None:
            playas_omitidas += 1
            logging.warning(
                f"Sin datos para la playa {id_playa}. Se continúa con la siguiente."
            )
            continue

        ahora = datetime.now(timezone.utc)
        ruta_particion = (
            f"year={ahora.year}/month={ahora.month:02d}/day={ahora.day:02d}"
        )
        s3_key = (
            f"{PREFIJO_PREDICCIONES}/{ruta_particion}/"
            f"pred_playa_{id_playa}_{ahora.strftime('%H%M%S')}.json"
        )

        try:
            subir_json_memoria(datos, S3_BUCKET_NAME, s3_key)
            archivos_subidos += 1
        except Exception:
            errores_subida += 1
            logging.exception(
                f"No se pudo subir la predicción de la playa {id_playa}."
            )

    # ── 5. Resumen final ─────────────────────────────────────────────────────
    logging.info("=== Pipeline finalizado ===")
    logging.info(
        f"Archivos subidos: {archivos_subidos} | "
        f"Playas omitidas: {playas_omitidas} | "
        f"Errores de subida: {errores_subida}"
    )


if __name__ == "__main__":
    main()
