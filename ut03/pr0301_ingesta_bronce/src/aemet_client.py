import time
import logging
import requests

def obtener_prediccion(id_playa, api_key):
    """
    Realiza el doble salto contra la API de AEMET y devuelve el JSON
    con la predicción meteorológica de la playa indicada.
    Devuelve None si hay error, sin detener la ejecución.
    """
    url_endpoint = f"https://opendata.aemet.es/opendata/api/prediccion/especifica/playa/{id_playa}"
    headers = {"api_key": api_key, "Accept": "application/json"}

    try:
        # PASO 1: Petición inicial para obtener la URL temporal
        resp_control = requests.get(url_endpoint, headers=headers, timeout=10)

        if resp_control.status_code == 429:
            logging.warning(f"Límite de peticiones alcanzado (429) para playa {id_playa}. Esperando 5s...")
            time.sleep(5)
            return None

        if resp_control.status_code == 404:
            logging.warning(f"Playa {id_playa} no encontrada en AEMET (404). Saltando...")
            return None

        resp_control.raise_for_status()
        info_control = resp_control.json()

        if info_control.get("estado") != 200:
            logging.warning(f"AEMET devolvió estado {info_control.get('estado')} para playa {id_playa}. Saltando...")
            return None

        # PASO 2: Descarga de los datos reales desde la URL temporal
        url_datos = info_control["datos"]
        resp_datos = requests.get(url_datos, timeout=10)
        resp_datos.raise_for_status()

        # Forzamos codificación para conservar tildes y eñes
        resp_datos.encoding = "ISO-8859-15"
        return resp_datos.json()

    except requests.exceptions.Timeout:
        logging.warning(f"Timeout al consultar playa {id_playa}. Saltando...")
        return None
    except Exception as e:
        logging.error(f"Error inesperado con playa {id_playa}: {e}")
        return None
    finally:
        # Pausa siempre para no saturar la cuota de AEMET
        time.sleep(1.5)