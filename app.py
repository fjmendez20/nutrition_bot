from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
import asyncio
from threading import Thread
from waitress import serve
import queue

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))

# Cola para procesar updates
update_queue = queue.Queue()

class BotManager:
    def __init__(self):
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .build()
        )
        
        # Configurar handlers
        from handlers import setup_handlers
        setup_handlers(self.application)

    async def setup_webhook(self):
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"Webhook configurado correctamente en {webhook_url}")

    async def process_update(self, update_data):
        """Procesa una actualización de manera asíncrona"""
        try:
            update = Update.de_json(update_data, self.application.bot)
            await self.application.process_update(update)
            return True
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}", exc_info=True)
            return False

# Inicialización del bot
bot_manager = BotManager()

@app.route('/')
def home():
    return "¡Bot activo! Webhook configurado en /webhook"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para actualizaciones de Telegram"""
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
    
    try:
        # Añadir el update a la cola para procesamiento
        update_queue.put(request.get_json())
        return "ok", 200
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

async def bot_processor():
    """Procesa updates de la cola de manera asíncrona"""
    while True:
        try:
            update_data = update_queue.get()
            await bot_manager.process_update(update_data)
            update_queue.task_done()
        except Exception as e:
            logger.error(f"Error en bot_processor: {str(e)}", exc_info=True)

def run_bot():
    """Inicia el bot y el procesador de updates"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Configurar webhook
    loop.run_until_complete(bot_manager.setup_webhook())
    
    # Iniciar procesador de updates
    loop.create_task(bot_processor())
    
    logger.info("Bot iniciado y listo para recibir actualizaciones")
    loop.run_forever()

def run_flask():
    """Inicia el servidor web"""
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Iniciar el bot en un hilo separado
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Iniciar Flask en el hilo principal
    run_flask()