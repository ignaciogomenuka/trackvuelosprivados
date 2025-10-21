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
- ✅ Alertas por Telegram cuando aviones entran/salen del radar
- ✅ Interface web en `/` para verificación manual
- ✅ API REST en `/api/check`
- ✅ Health check en `/status`
- ✅ Deploy listo para Railway/Heroku

El sistema funciona 24/7 automáticamente una vez deployado.