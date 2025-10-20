# Monitor de Vuelos Privados

Script en Python que monitorea en tiempo real si alguno de tus aviones registrados está volando y envía alertas por consola y opcionalmente por Telegram.

## Matrículas monitoreadas
- LV-FVZ
- LV-FUF
- LV-KMA
- LV-CCO

## Instalación

1. Crear entorno virtual e instalar dependencias:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configurar variables de entorno (opcional para Telegram):
```bash
cp .env.example .env
# Editar .env con tu TELEGRAM_TOKEN y TELEGRAM_CHAT_ID
```

## Uso

```bash
source venv/bin/activate
python monitor_vuelos.py
```

El script:
- Consulta la API de OpenSky Network cada 5 minutos
- Detecta cuando un avión entra o sale del radar
- Muestra información de altitud, velocidad y posición
- Envía notificaciones por Telegram si está configurado

Presiona `Ctrl+C` para detener el monitoreo.