# Monitor de Vuelos Privados

Aplicación web que monitorea en tiempo real si alguno de tus aviones registrados está volando y envía alertas por Telegram.

## Matrículas monitoreadas
- LV-FVZ
- LV-FUF
- LV-KMA
- LV-CCO
- LV-KAX

## Deployment en Railway

### Variables de entorno requeridas:
```
TELEGRAM_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
```

### Deploy automático:
1. Conecta este repo a Railway
2. Configura las variables de entorno
3. Deploy automático - Railway detectará Flask y usará gunicorn

## Uso local

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tu TELEGRAM_TOKEN y TELEGRAM_CHAT_ID
```

3. Ejecutar:
```bash
python app.py
```

## Funcionalidades

- ✅ Monitoreo automático cada 5 minutos en background
- ✅ **Multi-fuente: ADSB.one (primario) + OpenSky Network (respaldo)**
- ✅ Mejor cobertura global, especialmente en Sudamérica
- ✅ **Notificaciones inteligentes:**
  - 🔄 Vuelos **en curso** al iniciar el sistema
  - ✈️ Notificación al **despegar**
  - 🛬 Notificación al **aterrizar**
- ✅ **Info contextual en notificaciones:**
  - 📍 Aeropuerto más cercano (distancia)
  - ⏱️ ETA aproximado al aeropuerto cercano
  - 📊 Altitud, velocidad, posición
  - 🧭 Rumbo con dirección cardinal (N/S/E/W)
  - ⬆️⬇️ Velocidad vertical (subiendo/descendiendo/estable)
  - 🎯 Dirección estimada (hacia qué aeropuerto se dirige)
  - 🔗 Link directo a FlightRadar24
  - 🆘 Alertas de emergencia (squawk 7700/7600/7500)
- ✅ Persistencia de estado (sobrevive reinicios)
- ✅ Interface web en `/` para verificación manual
- ✅ API REST en `/api/check`
- ✅ Health check en `/status`
- ✅ Historial de vuelos con tabla
- ✅ Deploy listo para Railway/Heroku

El sistema funciona 24/7 automáticamente una vez deployado.

## Fuentes de datos

**ADSB.one** (API primaria):
- Mejor cobertura global
- Sin autenticación requerida
- Límite: 1 request/segundo
- Consulta individual por ICAO24

**OpenSky Network** (respaldo):
- Se usa si ADSB.one no detecta el avión
- Cubre todos los aviones en una sola consulta
- Puede tener cobertura limitada en ciertas regiones