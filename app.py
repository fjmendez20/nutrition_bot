from telegram.ext import ApplicationBuilder
from config import Config
import logging
import asyncio
import os
from flask import Flask, request, jsonify

# Configuración básica de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicialización de Flask
app = Flask(__name__)

# Crear la aplicación del bot (global para acceso desde Flask)
application = (
    ApplicationBuilder()
    .token(Config.TELEGRAM_TOKEN)
    .arbitrary_callback_data(True)
    .build()
)

# Importar y configurar handlers
from handlers import setup_handlers
setup_handlers(application)

# Rutas de Flask
@app.route('/')
def home():
    return "¡Bot activo con webhook!"

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Endpoint para recibir actualizaciones de Telegram"""
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
    return "ok", 200

async def set_webhook():
    """Configura el webhook en Telegram"""
    webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=Config.WEBHOOK_SECRET
    )
    logger.info(f"Webhook configurado en: {webhook_url}")

def run_flask():
    """Inicia el servidor Flask"""
    app.run(host='0.0.0.0', port=8081)

def main():
    # Configurar el webhook al iniciar
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(set_webhook())
    
    # Iniciar Flask (ya no en segundo plano)
    run_flask()

if __name__ == '__main__':
    main()