from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request
from waitress import serve
import asyncio
import threading
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
        self.initialized = False
        self.application = None
        
    def initialize(self):
        """Inicializa el bot de manera segura"""
        self.application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_TOKEN)
            .arbitrary_callback_data(True)
            .build()
        )
        
        # Configurar handlers
        from handlers import setup_handlers
        setup_handlers(self.application)
        
        self.initialized = True
        logger.info("Bot inicializado correctamente")

    async def setup_webhook(self):
        """Configura el webhook"""
        if not self.initialized:
            self.initialize()
            
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.initialize()
        await self.application.start()
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"Webhook configurado en: {webhook_url}")

    async def process_update(self, update_data):
        """Procesa una actualización"""
        try:
            if not self.initialized:
                self.initialize()
                await self.application.initialize()
                await self.application.start()
                
            update = Update.de_json(update_data, self.application.bot)
            await self.application.process_update(update)
            return True
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}", exc_info=True)
            return False

# Instancia global del bot
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
        update_queue.put(request.get_json())
        return "ok", 200
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return "server error", 500

async def process_updates():
    """Procesa updates de la cola"""
    while True:
        try:
            update_data = update_queue.get()
            await bot_manager.process_update(update_data)
            update_queue.task_done()
        except Exception as e:
            logger.error(f"Error en process_updates: {str(e)}", exc_info=True)

def run_bot():
    """Inicia el bot en un event loop separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Configuración inicial
    loop.run_until_complete(bot_manager.setup_webhook())
    
    # Procesador de updates
    loop.create_task(process_updates())
    
    logger.info("Bot iniciado y listo para recibir actualizaciones")
    loop.run_forever()

def run_flask():
    """Inicia el servidor web"""
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Inicia el bot en un hilo separado
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Inicia Flask en el hilo principal
    run_flask()