import requests
import time
import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from math import radians, cos, sin, asin, sqrt, atan2, degrees

load_dotenv()

ARGENTINA_TZ = timezone(timedelta(hours=-3))

PLANES = {
    "e0659a": "LV-FVZ",
    "e030cf": "LV-CCO",
    "e06546": "LV-FUF",
    "e0b341": "LV-KMA",
    "e0b058": "LV-KAX",
}

active_planes = set()
notified_planes = set()
STATE_FILE = "plane_state.json"
HISTORY_FILE = "flight_history.json"

ARGENTINA_AIRPORTS = {
    "SAEZ": {"name": "Ezeiza", "lat": -34.8222, "lon": -58.5358},
    "SABE": {"name": "Aeroparque", "lat": -34.5592, "lon": -58.4156},
    "SACO": {"name": "Córdoba", "lat": -31.3233, "lon": -64.2080},
    "SAZS": {"name": "San Carlos de Bariloche", "lat": -41.1512, "lon": -71.1575},
    "SAZM": {"name": "Mendoza", "lat": -32.8317, "lon": -68.7929},
    "SASA": {"name": "Salta", "lat": -24.8560, "lon": -65.4862},
    "SARF": {"name": "Rosario", "lat": -32.9036, "lon": -60.7850},
    "SAAV": {"name": "Ushuaia", "lat": -54.8433, "lon": -68.2958},
}

def load_state():
    global notified_planes, active_planes
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                notified_planes = set(state.get('notified_planes', []))
                active_planes = set(state.get('active_planes', []))
        except:
            notified_planes = set()
            active_planes = set()

def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'notified_planes': list(notified_planes),
                'active_planes': list(active_planes)
            }, f, indent=2)
    except Exception as e:
        print(f"Error guardando estado: {e}")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_flight_event(callsign, event_type, data=None):
    history = load_history()
    event = {
        "callsign": callsign,
        "type": event_type,
        "timestamp": datetime.now(ARGENTINA_TZ).isoformat(),
        "data": data or {}
    }
    history.insert(0, event)
    history = history[:100]

    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")

def calculate_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

def find_nearest_airport(lat, lon):
    if lat == "N/A" or lon == "N/A":
        return None

    nearest = None
    min_distance = float('inf')

    for code, airport in ARGENTINA_AIRPORTS.items():
        distance = calculate_distance(lat, lon, airport['lat'], airport['lon'])
        if distance < min_distance:
            min_distance = distance
            nearest = {"code": code, "name": airport['name'], "distance": round(distance, 1)}

    return nearest

def calculate_eta(distance_km, speed_kmh):
    if speed_kmh and speed_kmh != "N/A" and speed_kmh > 0:
        hours = distance_km / speed_kmh
        minutes = int(hours * 60)
        return f"{minutes} min"
    return "N/A"

def get_cardinal_direction(heading):
    if heading == "N/A":
        return ""
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    idx = int((heading + 22.5) / 45) % 8
    return directions[idx]

def get_vertical_status(baro_rate):
    if baro_rate == "N/A":
        return ""
    if baro_rate > 64:
        return f"⬆️ Subiendo +{baro_rate} ft/min"
    elif baro_rate < -64:
        return f"⬇️ Descendiendo {baro_rate} ft/min"
    else:
        return "➡️ Altitud estable"

def check_emergency(squawk):
    if squawk == "7700":
        return "🆘 EMERGENCIA"
    elif squawk == "7600":
        return "📻 Falla de radio"
    elif squawk == "7500":
        return "🚨 HIJACK"
    return None

def calculate_heading_to_airport(lat, lon, airport_lat, airport_lon):
    lat1, lon1, lat2, lon2 = map(radians, [lat, lon, airport_lat, airport_lon])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    bearing = degrees(atan2(x, y))
    return (bearing + 360) % 360

def find_destination_airport(lat, lon, heading):
    if lat == "N/A" or lon == "N/A" or heading == "N/A":
        return None

    min_angle_diff = float('inf')
    destination = None

    for code, airport in ARGENTINA_AIRPORTS.items():
        bearing = calculate_heading_to_airport(lat, lon, airport['lat'], airport['lon'])
        angle_diff = abs(((bearing - heading + 180) % 360) - 180)

        if angle_diff < 45 and angle_diff < min_angle_diff:
            distance = calculate_distance(lat, lon, airport['lat'], airport['lon'])
            if distance > 5:
                min_angle_diff = angle_diff
                destination = {"code": code, "name": airport['name'], "distance": round(distance, 1)}

    return destination

def notify_telegram(msg):
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

def check_opensky():
    results = {}
    try:
        response = requests.get("https://opensky-network.org/api/states/all", timeout=30)
        if response.status_code == 200:
            data = response.json()
            for state in data.get("states", []):
                if len(state) < 14:
                    continue
                icao24 = state[0].lower() if state[0] else None
                if icao24 in PLANES:
                    vertical_ms = state[11] if state[11] is not None else None
                    baro_rate_fpm = round(vertical_ms * 196.85) if vertical_ms else "N/A"

                    results[icao24] = {
                        "icao24": icao24,
                        "callsign": state[1].strip() if state[1] else "",
                        "altitude": state[13] if state[13] is not None else "N/A",
                        "velocity": round(state[9] * 3.6, 1) if state[9] is not None else "N/A",
                        "country": state[2] if state[2] else "N/A",
                        "lat": state[6] if state[6] is not None else "N/A",
                        "lon": state[5] if state[5] is not None else "N/A",
                        "heading": state[10] if state[10] is not None else "N/A",
                        "baro_rate": baro_rate_fpm,
                        "squawk": "",
                        "source": "OpenSky"
                    }
    except Exception as e:
        print(f"OpenSky error: {e}")
    return results

def check_flights():
    global active_planes
    currently_flying = set()

    now_arg = datetime.now(ARGENTINA_TZ)
    print(f"{now_arg.strftime('%Y-%m-%d %H:%M:%S %Z')} - Verificando vuelos...")
    opensky_results = check_opensky()

    for icao24, registration in PLANES.items():
        if icao24 in opensky_results:
            currently_flying.add(registration)
            plane_data = opensky_results[icao24]

            if registration not in active_planes:
                altitude_unit = "m"
                velocity_unit = "km/h"

                nearest = find_nearest_airport(plane_data['lat'], plane_data['lon'])
                destination = find_destination_airport(plane_data['lat'], plane_data['lon'], plane_data.get('heading', 'N/A'))

                is_in_progress = registration in notified_planes
                event_icon = "🔄" if is_in_progress else "✈️"
                event_type = "en curso" if is_in_progress else "despegó"

                msg = f"{event_icon} {registration} {event_type}\n"
                msg += f"ICAO24: {icao24}\n"

                emergency = check_emergency(plane_data.get('squawk', ''))
                if emergency:
                    msg += f"{emergency}\n"

                msg += f"\n📊 Altitud: {plane_data['altitude']} {altitude_unit}\n"
                msg += f"🚀 Velocidad: {plane_data['velocity']} {velocity_unit}\n"

                heading = plane_data.get('heading', 'N/A')
                if heading != "N/A":
                    cardinal = get_cardinal_direction(heading)
                    msg += f"🧭 Rumbo: {int(heading)}° ({cardinal})\n"

                vertical = get_vertical_status(plane_data.get('baro_rate', 'N/A'))
                if vertical:
                    msg += f"{vertical}\n"

                if nearest:
                    msg += f"\n📍 Aeropuerto más cercano: {nearest['name']} ({nearest['code']})\n"
                    msg += f"📏 Distancia: {nearest['distance']} km\n"

                    eta = calculate_eta(nearest['distance'], plane_data['velocity'])
                    if eta != "N/A":
                        msg += f"⏱️ ETA aproximado: {eta}\n"

                if destination and destination['name'] != (nearest['name'] if nearest else None):
                    msg += f"🎯 Dirección estimada: Hacia {destination['name']} ({destination['distance']} km)\n"

                msg += f"\n🔗 Ver en vivo: https://www.flightradar24.com/{registration}\n"
                msg += f"\n📡 Fuente: {plane_data['source']}\n"
                msg += f"🕐 {now_arg.strftime('%Y-%m-%d %H:%M:%S %Z')}"

                notify_telegram(msg)
                notified_planes.add(registration)
                save_state()

                save_flight_event(registration, "in_progress" if is_in_progress else "takeoff", {
                    "icao24": icao24,
                    "altitude": plane_data["altitude"],
                    "velocity": plane_data["velocity"],
                    "lat": plane_data["lat"],
                    "lon": plane_data["lon"],
                    "source": plane_data["source"],
                    "nearest_airport": nearest['name'] if nearest else None
                })

    for plane in active_planes - currently_flying:
        msg = (f"🛬 {plane} aterrizó\n"
               f"🕐 {now_arg.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        notify_telegram(msg)
        save_flight_event(plane, "landing")

        if plane in notified_planes:
            notified_planes.remove(plane)
            save_state()

    active_planes = currently_flying
    save_state()
    print(f"{now_arg.strftime('%Y-%m-%d %H:%M:%S %Z')} - Verificación completada. Aviones en vuelo: {len(currently_flying)}")

def main():
    load_state()
    print(f"Iniciando monitoreo de vuelos...")
    print(f"Matrículas monitoreadas: {', '.join(PLANES.values())}")
    print(f"Estado cargado. Aviones previamente notificados: {notified_planes}")
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
