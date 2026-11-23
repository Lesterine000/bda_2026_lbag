import json
import logging
import time

import requests

URL_BASE = "https://opendata.aemet.es/opendata/api/prediccion/especifica/playa"
TIMEOUT_SEGUNDOS = 10
PAUSA_SEGUNDOS = 1.5


def _decodificar_json(respuesta):
    """Decodifica el JSON conservando tildes y eñes.

    AEMET no siempre declara el charset en la cabecera Content-Type. Probamos
    primero UTF-8 (lo habitual) y, si falla, ISO-8859-15/cp1252, que es la
    codificación que utiliza AEMET OpenData en algunas respuestas.
    """
    for encoding in ("utf-8-sig", "utf-8", "ISO-8859-15", "cp1252"):
        try:
            return json.loads(respuesta.content.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    # Último recurso: que requests decodifique según sus propias reglas
    return respuesta.json()


def obtener_prediccion(id_playa, api_key):
    """Realiza el doble salto contra la API de AEMET.

    Devuelve el JSON con la predicción meteorológica de la playa indicada o
    None si hay cualquier error (404, 429, timeout, etc.). En ningún caso
    detiene la ejecución del pipeline.
    """
    id_playa = str(id_playa).strip().zfill(7)
    if len(id_playa) != 7 or not id_playa.isdigit():
        logging.warning(
            f"ID de playa no válido: '{id_playa}'. Se esperaban 7 dígitos. "
            "Saltando..."
        )
        return None

    url_endpoint = f"{URL_BASE}/{id_playa}"
    headers = {"api_key": api_key, "Accept": "application/json"}

    try:
        # PASO 1: petición inicial para obtener la URL temporal de los datos
        resp_control = requests.get(
            url_endpoint, headers=headers, timeout=TIMEOUT_SEGUNDOS
        )

        if resp_control.status_code == 429:
            logging.warning(
                f"Límite de peticiones alcanzado (429) para la playa {id_playa}. "
                "Esperando 5 segundos antes de continuar..."
            )
            time.sleep(5)
            return None

        if resp_control.status_code == 404:
            logging.warning(
                f"La playa {id_playa} no tiene predicción disponible en AEMET "
                "(404). Saltando..."
            )
            return None

        resp_control.raise_for_status()
        info_control = resp_control.json()

        # AEMET devuelve un estado interno dentro del JSON de control
        if str(info_control.get("estado")) != "200":
            logging.warning(
                f"AEMET devolvió el estado {info_control.get('estado')} para la "
                f"playa {id_playa}. Saltando..."
            )
            return None

        url_datos = info_control.get("datos")
        if not url_datos:
            logging.warning(
                f"La respuesta de AEMET no incluye URL de datos para la playa "
                f"{id_playa}. Saltando..."
            )
            return None

        # PASO 2: descarga de los datos reales desde la URL temporal
        resp_datos = requests.get(url_datos, timeout=TIMEOUT_SEGUNDOS)
        resp_datos.raise_for_status()

        datos = _decodificar_json(resp_datos)
        logging.info(f"Predicción descargada correctamente para la playa {id_playa}.")
        return datos

    except requests.exceptions.Timeout:
        logging.warning(f"Timeout al consultar la playa {id_playa}. Saltando...")
        return None
    except requests.exceptions.HTTPError as error:
        logging.warning(
            f"Error HTTP al consultar la playa {id_playa}: {error}. Saltando..."
        )
        return None
    except requests.exceptions.RequestException as error:
        logging.warning(
            f"Error de conexión con AEMET para la playa {id_playa}: {error}. "
            "Saltando..."
        )
        return None
    except Exception as error:
        logging.error(f"Error inesperado con la playa {id_playa}: {error}")
        return None
    finally:
        # Pausa entre llamadas para no superar la cuota de AEMET (HTTP 429)
        time.sleep(PAUSA_SEGUNDOS)
