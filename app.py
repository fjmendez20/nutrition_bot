from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
from waitress import serve
import asyncio

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 10000))

class BotManager:
    def __init__(self):
        self.application = None
        
    async def initialize(self):
        if self.application is None:
            self.application = (
                ApplicationBuilder()
                .token(Config.TELEGRAM_TOKEN)
                .arbitrary_callback_data(True)
                .post_init(self.post_init)  # Añade esta línea
                .build()
            )
            from handlers import setup_handlers
            setup_handlers(self.application)
            
            await self.application.initialize()
            await self.application.start()
            logger.info("Bot inicializado correctamente")

    async def post_init(self, application):
        """Callback después de la inicialización"""
        logger.info("Verificando handlers registrados:")
        for handler in application.handlers[0]:
            logger.info(f"Handler: {type(handler).__name__}, pattern: {getattr(handler, 'pattern', 'N/A')}")

    async def setup_webhook(self):
        await self.initialize()
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"Webhook configurado en: {webhook_url}")

    async def process_update(self, update_data):
        try:
            if self.application is None:
                await self.initialize()
            
            update = Update.de_json(update_data, self.application.bot)
            await self.application.process_update(update)
            return True
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}", exc_info=True)
            return False

bot_manager = BotManager()

@app.route('/')
def home():
    return "¡Bot activo! Webhook configurado en /webhook"

@app.post('/webhook')
async def webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
    
    update_data = request.get_json()
    logger.info(f"Update recibido: {update_data}")
    
    success = await bot_manager.process_update(update_data)
    return "ok" if success else "error", 200

@app.get('/webhook_status')
async def webhook_status():
    if bot_manager.application is None:
        return jsonify({"status": "Bot no inicializado"}), 503
    
    info = await bot_manager.application.bot.get_webhook_info()
    return jsonify({
        'url': info.url,
        'pending_updates': info.pending_update_count,
        'last_error': info.last_error_message
    })

def run_flask():
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

async def startup():
    await bot_manager.setup_webhook()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(startup())
    run_flask()