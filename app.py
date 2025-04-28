from telegram.ext import ApplicationBuilder, Application
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
import asyncio
from threading import Thread

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))  # Render usa 10000 por defecto

# Inicialización del bot
application: Application = (
    ApplicationBuilder()
    .token(Config.TELEGRAM_TOKEN)
    .arbitrary_callback_data(True)
    .build()
)

# Handlers
from handlers import setup_handlers
setup_handlers(application)

@app.route('/')
def home():
    return "¡Bot activo! Ver /webhook_info para estado del webhook"

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Endpoint para actualizaciones de Telegram"""
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
        
    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, application.bot)
        await application.update_queue.put(update)  # Método recomendado para PTB v20+
        return "ok", 200
    except Exception as e:
        logger.error(f"Error procesando update: {e}", exc_info=True)
        return "server error", 500

@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """Obtiene información del webhook actual (síncrono para Flask)"""
    try:
        info = asyncio.run_coroutine_threadsafe(
            application.bot.get_webhook_info(),
            application.updater._event_loop  # Acceso al event loop
        ).result()
        
        return jsonify({
            "url": info.url,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "status": "active" if info.url else "inactive"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

async def setup_webhook():
    """Configuración asíncrona del webhook"""
    webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=Config.WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]  # Especifica los updates que necesitas
    )
    logger.info(f"Webhook configurado en: {webhook_url}")
    logger.info(f"Webhook info: {await application.bot.get_webhook_info()}")

def run_flask():
    """Inicia Flask en el puerto correcto"""
    # Usar waitress como servidor de producción (añádelo a requirements.txt)
    from waitress import serve
    serve(app, host='0.0.0.0', port=PORT)

def run_bot():
    """Inicia el bot en un event loop separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook())
    loop.run_forever()  # Mantiene el bot activo

if __name__ == '__main__':
    # Hilo para el bot (PTB necesita su propio event loop)
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Inicia Flask (en el hilo principal)
    run_flask()