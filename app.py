from flask import Flask, jsonify, render_template_string
import requests
import os
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

PLANES = ["LVFVZ", "LVFUF", "LVKMA", "LVCCO"]
active_planes = set()

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

        for plane in active_planes - currently_flying:
            msg = (f"🛬 {plane} ya no está en vuelo\n"
                   f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            notify_telegram(msg)

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
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .plane { background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .flying { background: #e7f5e7; border-left: 4px solid #28a745; }
        .status { font-weight: bold; color: #28a745; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .timestamp { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>🛩️ Monitor de Vuelos Privados</h1>
    <p>Monitoreo en tiempo real de las matrículas: LV-FVZ, LV-FUF, LV-KMA, LV-CCO</p>

    <button onclick="checkFlights()">🔄 Verificar Vuelos</button>

    <div id="status"></div>
    <div id="results"></div>

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
                    let html = `<h3>✈️ Aviones en vuelo (${data.planes_en_vuelo})</h3>`;
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

        checkFlights();
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