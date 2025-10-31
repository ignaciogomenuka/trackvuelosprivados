from flask import Flask, jsonify, render_template_string
import requests
import os
import threading
import time
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

ARGENTINA_TZ = timezone(timedelta(hours=-3))

app = Flask(__name__)

PLANES = {
    "e0659a": "LV-FVZ",
    "e030cf": "LV-CCO",
    "e06546": "LV-FUF",
    "e0b341": "LV-KMA",
    "e0b058": "LV-KAX",
}

active_planes = set()
notified_planes = set()
HISTORY_FILE = "flight_history.json"
STATE_FILE = "plane_state.json"

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

def calculate_distance(lat1, lon1, lat2, lon2):
    from math import radians, cos, sin, asin, sqrt
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
    from math import atan2, degrees, radians, cos, sin
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

def check_adsb_one(icao24):
    try:
        print(f"  Consultando ADSB.one para {icao24}...")
        response = requests.get(f"https://api.adsb.one/v2/hex/{icao24}", timeout=5)
        print(f"  ADSB.one {icao24}: status {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get("total", 0) > 0 and data.get("ac"):
                aircraft = data["ac"][0]
                return {
                    "icao24": aircraft.get("hex", "").lower(),
                    "callsign": aircraft.get("flight", "").strip() or aircraft.get("r", ""),
                    "altitude": aircraft.get("alt_baro", "N/A"),
                    "velocity": round(aircraft.get("gs", 0) * 1.852, 1) if aircraft.get("gs") else "N/A",
                    "country": "N/A",
                    "lat": aircraft.get("lat", "N/A"),
                    "lon": aircraft.get("lon", "N/A"),
                    "heading": aircraft.get("track", "N/A"),
                    "baro_rate": aircraft.get("baro_rate", "N/A"),
                    "squawk": aircraft.get("squawk", ""),
                    "source": "ADSB.one"
                }
    except Exception as e:
        print(f"ADSB.one error for {icao24}: {e}")
    return None

def check_opensky():
    results = {}
    try:
        print(f"Consultando OpenSky Network...")
        response = requests.get("https://opensky-network.org/api/states/all", timeout=30)
        print(f"OpenSky response: status {response.status_code}")
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
    planes_info = []

    # Prioritize OpenSky (single call, more reliable)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Checking OpenSky Network...")
    opensky_results = check_opensky()

    for icao24, registration in PLANES.items():
        if icao24 in opensky_results:
            currently_flying.add(registration)
            plane_data = opensky_results[icao24]
            plane_data["callsign"] = registration
            planes_info.append(plane_data)
            print(f"  Found {registration} via OpenSky")

    # Only check ADSB.one for planes not found in OpenSky
    if len(currently_flying) < len(PLANES):
        print(f"OpenSky found {len(currently_flying)}/{len(PLANES)} planes. Checking ADSB.one for missing planes...")
        for icao24, registration in PLANES.items():
            if registration not in currently_flying:
                try:
                    plane_data = check_adsb_one(icao24)
                    if plane_data:
                        currently_flying.add(registration)
                        plane_data["callsign"] = registration
                        planes_info.append(plane_data)
                        print(f"  Found {registration} via ADSB.one")
                except Exception as e:
                    print(f"  Error checking {registration} on ADSB.one: {e}")
                time.sleep(0.5)

    for plane_data in planes_info:
        registration = plane_data["callsign"]
        icao24 = plane_data["icao24"]

        if registration not in active_planes:
            altitude_unit = "m" if plane_data["source"] == "OpenSky" else "ft"
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
            msg += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

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
               f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        notify_telegram(msg)
        save_flight_event(plane, "landing")

        if plane in notified_planes:
            notified_planes.remove(plane)
            save_state()

    active_planes = currently_flying
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Verificación completada. Aviones en vuelo: {len(currently_flying)}")

    return planes_info

def monitor_flights():
    while True:
        check_flights()
        time.sleep(300)  # 5 minutos

@app.route('/')
def index():
    html = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor de Vuelos Privados</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .plane { background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .flying { background: #e7f5e7; border-left: 4px solid #28a745; }
        .status { font-weight: bold; color: #28a745; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #0056b3; }
        .timestamp { color: #666; font-size: 0.9em; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #007bff; color: white; font-weight: bold; }
        tr:hover { background: #f5f5f5; }
        .takeoff { color: #28a745; font-weight: bold; }
        .landing { color: #dc3545; font-weight: bold; }
        .section { margin: 30px 0; }
        h2 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
    </style>
</head>
<body>
    <h1>🛩️ Monitor de Vuelos Privados</h1>
    <p>Monitoreo en tiempo real de las matrículas: LV-FVZ, LV-CCO, LV-FUF, LV-KMA, LV-KAX</p>
    <p style="font-size: 0.85em; color: #666;">Multi-fuente: ADSB.one + OpenSky Network | Detección vía ICAO24 Mode-S</p>

    <div>
        <button onclick="checkFlights()">🔄 Verificar Vuelos</button>
        <button onclick="loadHistory()">📋 Ver Historial</button>
    </div>

    <div id="status"></div>

    <div class="section" id="results"></div>

    <div class="section" id="history-section" style="display: none;">
        <h2>📊 Historial de Vuelos</h2>
        <div id="history"></div>
    </div>

    <script>
        async function checkFlights() {
            document.getElementById('status').innerHTML = '<p>🔍 Consultando API...</p>';

            try {
                const response = await fetch('/api/check');
                const data = await response.json();

                document.getElementById('status').innerHTML = `
                    <p class="timestamp">Última verificación: ${data.timestamp}</p>
                `;

                const resultsDiv = document.getElementById('results');

                if (data.planes_en_vuelo > 0) {
                    let html = `<h2>✈️ Aviones en vuelo (${data.planes_en_vuelo})</h2>`;
                    data.aviones.forEach(plane => {
                        html += `
                            <div class="plane flying">
                                <div class="status">🟢 ${plane.callsign} EN VUELO</div>
                                <p>Altitud: ${plane.altitude} m | Velocidad: ${plane.velocity} km/h</p>
                                <p>País: ${plane.country} | Posición: ${plane.lat}, ${plane.lon}</p>
                            </div>
                        `;
                    });
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = `
                        <h2>Estado Actual</h2>
                        <div class="plane">
                            <div class="status">🔴 Ningún avión en vuelo</div>
                            <p>No se detectaron vuelos activos para las matrículas monitoreadas.</p>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('results').innerHTML = `
                    <div class="plane" style="background: #f8d7da; border-left: 4px solid #dc3545;">
                        <div style="color: #721c24;">❌ Error al consultar API</div>
                        <p>No se pudo conectar con el servicio de monitoreo.</p>
                    </div>
                `;
            }
        }

        async function loadHistory() {
            const historySection = document.getElementById('history-section');
            historySection.style.display = 'block';
            document.getElementById('history').innerHTML = '<p>⏳ Cargando historial...</p>';

            try {
                const response = await fetch('/api/history');
                const data = await response.json();

                if (data.total === 0) {
                    document.getElementById('history').innerHTML = '<p>No hay eventos registrados aún.</p>';
                    return;
                }

                let html = `
                    <table>
                        <thead>
                            <tr>
                                <th>Matrícula</th>
                                <th>Evento</th>
                                <th>Fecha y Hora</th>
                                <th>Detalles</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                data.events.forEach(event => {
                    const date = new Date(event.timestamp);
                    const formattedDate = date.toLocaleString('es-AR');
                    const eventType = event.type === 'takeoff' ? '✈️ Despegue' : '🛬 Aterrizaje';
                    const eventClass = event.type === 'takeoff' ? 'takeoff' : 'landing';

                    let details = '';
                    if (event.data && event.data.altitude) {
                        details = `Alt: ${event.data.altitude}m, Vel: ${event.data.velocity} km/h`;
                    }

                    html += `
                        <tr>
                            <td><strong>${event.callsign}</strong></td>
                            <td class="${eventClass}">${eventType}</td>
                            <td>${formattedDate}</td>
                            <td>${details}</td>
                        </tr>
                    `;
                });

                html += '</tbody></table>';
                document.getElementById('history').innerHTML = html;

            } catch (error) {
                document.getElementById('history').innerHTML = `
                    <p style="color: #dc3545;">❌ Error al cargar el historial</p>
                `;
            }
        }

        checkFlights();
        loadHistory();
    </script>
</body>
</html>
    '''
    return html

@app.route('/api/check')
def api_check():
    planes_info = check_flights()

    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "planes_monitoreados": PLANES,
        "planes_en_vuelo": len(planes_info),
        "aviones": planes_info
    })

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "service": "Flight Monitor v3.0 - Multi-Source",
        "planes_monitoreados": PLANES,
        "planes_activos": list(active_planes),
        "sources": ["ADSB.one (primary)", "OpenSky Network (backup)"],
        "timestamp": datetime.now().isoformat(),
        "url": "Railway deployment ready",
        "note": "Multi-source tracking via ADSB.one + OpenSky for better coverage"
    })

@app.route('/api/history')
def api_history():
    history = load_history()
    return jsonify({
        "total": len(history),
        "events": history
    })

@app.route('/test-telegram')
def test_telegram():
    try:
        test_message = (f"🧪 Test del sistema de monitoreo\n"
                       f"✅ Sistema funcionando correctamente\n"
                       f"📊 Planes monitoreados: {', '.join(PLANES)}\n"
                       f"🕐 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                       f"🔗 URL: trackvuelosprivados-production.up.railway.app")

        notify_telegram(test_message)

        return jsonify({
            "status": "success",
            "message": "Test message sent to Telegram",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

monitor_started = False

def start_monitor_thread():
    global monitor_started
    if not monitor_started:
        monitor_thread = threading.Thread(target=monitor_flights, daemon=True)
        monitor_thread.start()
        monitor_started = True
        print("✅ Monitor automático iniciado en thread background")
        print("📊 Verificando vuelos cada 5 minutos")
        return monitor_thread
    return None

load_state()
print(f"Estado cargado. Aviones previamente notificados: {notified_planes}")

enable_monitor = os.getenv('ENABLE_MONITOR', 'false').lower() == 'true'

if enable_monitor:
    print("🚀 Iniciando monitor automático...")
    start_monitor_thread()
else:
    print("⚠️ Monitor automático deshabilitado")
    print("Configure ENABLE_MONITOR=true para activar")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)