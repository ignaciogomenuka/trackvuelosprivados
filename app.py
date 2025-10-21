from flask import Flask, jsonify, render_template_string
import requests
import os
import threading
import time
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

PLANES = ["LVFVZ", "LVFUF", "LVKMA", "LVCCO"]
active_planes = set()
HISTORY_FILE = "flight_history.json"

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
        "timestamp": datetime.now().isoformat(),
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

def check_flights():
    global active_planes
    try:
        response = requests.get("https://opensky-network.org/api/states/all", timeout=30)
        data = response.json()

        currently_flying = set()
        planes_info = []

        for state in data.get("states", []):
            if len(state) < 14:
                continue

            callsign = state[1].strip().upper() if state[1] else None

            if callsign in PLANES:
                currently_flying.add(callsign)

                altitude = state[13] if state[13] is not None else "N/A"
                velocity = round(state[9] * 3.6, 1) if state[9] is not None else "N/A"
                lat = state[6] if state[6] is not None else "N/A"
                lon = state[5] if state[5] is not None else "N/A"
                country = state[2] if state[2] else "N/A"

                planes_info.append({
                    "callsign": callsign,
                    "altitude": altitude,
                    "velocity": velocity,
                    "country": country,
                    "lat": lat,
                    "lon": lon
                })

                if callsign not in active_planes:
                    msg = (f"✈️ {callsign} está en vuelo\n"
                           f"Altitud: {altitude} m\n"
                           f"Velocidad: {velocity} km/h\n"
                           f"País: {country}\n"
                           f"Posición: lat={lat}, lon={lon}\n"
                           f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    notify_telegram(msg)
                    save_flight_event(callsign, "takeoff", {
                        "altitude": altitude,
                        "velocity": velocity,
                        "country": country,
                        "lat": lat,
                        "lon": lon
                    })

        for plane in active_planes - currently_flying:
            msg = (f"🛬 {plane} ya no está en vuelo\n"
                   f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            notify_telegram(msg)
            save_flight_event(plane, "landing")

        active_planes = currently_flying

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Verificación completada. Aviones en vuelo: {len(currently_flying)}")

        return planes_info

    except Exception as e:
        print(f"Error en la verificación: {e}")
        return []

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
    <p>Monitoreo en tiempo real de las matrículas: LV-FVZ, LV-FUF, LV-KMA, LV-CCO</p>

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
        "service": "Flight Monitor v1.0",
        "planes_monitoreados": PLANES,
        "planes_activos": list(active_planes),
        "timestamp": datetime.now().isoformat(),
        "url": "Railway deployment ready"
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

if __name__ == '__main__':
    # Iniciar el monitor en un hilo separado
    monitor_thread = threading.Thread(target=monitor_flights, daemon=True)
    monitor_thread.start()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)