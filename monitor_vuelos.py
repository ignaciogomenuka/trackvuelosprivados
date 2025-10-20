import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PLANES = ["LVFVZ", "LVFUF", "LVKMA", "LVCCO"]
active_planes = set()

def notify(msg):
    print(msg)
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": msg}
            )
        except Exception as e:
            print(f"Error enviando mensaje por Telegram: {e}")

def check_flights():
    try:
        response = requests.get("https://opensky-network.org/api/states/all", timeout=30)
        data = response.json()

        currently_flying = set()

        for state in data.get("states", []):
            if len(state) < 14:
                continue

            callsign = state[1].strip().upper() if state[1] else None

            if callsign in PLANES:
                currently_flying.add(callsign)

                if callsign not in active_planes:
                    altitude = state[13] if state[13] is not None else "N/A"
                    velocity = round(state[9] * 3.6, 1) if state[9] is not None else "N/A"
                    lat = state[6] if state[6] is not None else "N/A"
                    lon = state[5] if state[5] is not None else "N/A"
                    country = state[2] if state[2] else "N/A"

                    msg = (f"✈️ {callsign} está en vuelo\n"
                           f"Altitud: {altitude} m\n"
                           f"Velocidad: {velocity} km/h\n"
                           f"País: {country}\n"
                           f"Posición: lat={lat}, lon={lon}\n"
                           f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    notify(msg)

        for plane in active_planes - currently_flying:
            msg = (f"🛬 {plane} ya no está en vuelo\n"
                   f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            notify(msg)

        active_planes.clear()
        active_planes.update(currently_flying)

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Verificación completada. Aviones en vuelo: {len(currently_flying)}")

    except Exception as e:
        print(f"Error en la verificación: {e}")

def main():
    print("Iniciando monitoreo de vuelos...")
    print(f"Matrículas monitoreadas: {', '.join(PLANES)}")
    print("Presiona Ctrl+C para detener el monitoreo\n")

    try:
        while True:
            check_flights()
            time.sleep(300)
    except KeyboardInterrupt:
        print("\nMonitoreo detenido por el usuario.")
    except Exception as e:
        print(f"Error fatal: {e}")

if __name__ == "__main__":
    main()