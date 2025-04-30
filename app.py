from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
import logging
import os
from flask import Flask, request, jsonify
from waitress import serve
import asyncio
from telegram.request import HTTPXRequest

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
        self.lock = asyncio.Lock()  # Para evitar race conditions
        
        # Configuración optimizada para Render
        self.request = HTTPXRequest(
            connection_pool_size=30,
            read_timeout=30.0,
            write_timeout=30.0,
            connect_timeout=30.0,
            pool_timeout=60.0,
            http_version="1.1",
            limits=httpx.Limits(
                max_connections=30,
                max_keepalive_connections=25,
                keepalive_expiry=60.0
            )
        )
    async def safe_shutdown(self):
        """Cierre seguro para Render"""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            self.application = None
    
    async def initialize(self):
        if self.application is None:
            self.application = (
                ApplicationBuilder()
                .token(Config.TELEGRAM_TOKEN)
                .arbitrary_callback_data(True)
                .request(self.request)  # Usamos nuestra configuración custom
                .post_init(self.post_init)
                .build()
            )
            
            from handlers import setup_handlers
            setup_handlers(self.application)
            
            await self.application.initialize()
            await self.application.start()
            logger.info("Bot inicializado correctamente")

    async def post_init(self, application):
        """Verificación después de inicializar"""
        logger.info("Handlers registrados:")
        for handler in application.handlers[0]:
            logger.info(f"- {type(handler).__name__}: {getattr(handler, 'pattern', 'N/A')}")

async def setup_webhook(self):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            await self.initialize()
            webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
            
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)
            
            await self.application.bot.set_webhook(
                url=webhook_url,
                secret_token=Config.WEBHOOK_SECRET,
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                max_connections=30
            )
            logger.info(f"Webhook configurado (intento {attempt + 1}): {webhook_url}")
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = (attempt + 1) * 5
            logger.warning(f"Intento {attempt + 1} fallido. Esperando {wait_time}s: {e}")
            await asyncio.sleep(wait_time)

    async def process_update(self, update_data):
        try:
            if self.application is None:
                await self.initialize()
            
            update = Update.de_json(update_data, self.application.bot)
            
            # Log para diagnóstico
            if update.callback_query:
                logger.info(f"Procesando callback: {update.callback_query.data}")
            
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
        return "Unauthorized", 401
    
    try:
        update_data = request.get_json()
        logger.info(f"Update recibido (type: {update_data.get('update_id')})")
        
        success = await bot_manager.process_update(update_data)
        return "ok" if success else "error", 200
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return "server error", 500

@app.get('/webhook_status')
async def webhook_status():
    if bot_manager.application is None:
        return jsonify({"status": "Bot no inicializado"}), 503
    
    info = await bot_manager.application.bot.get_webhook_info()
    return jsonify({
        'url': info.url,
        'pending_updates': info.pending_update_count,
        'last_error': info.last_error_message,
        'last_error_date': str(info.last_error_date)
    })
    
@app.get('/health')
async def health_check():
    try:
        if bot_manager.application:
            # Verifica conexión con Telegram
            await bot_manager.application.bot.get_me()
            return jsonify({
                "status": "healthy",
                "pool_connections": bot_manager.request._client._transport._pool._connections
            }), 200
        return jsonify({"status": "initializing"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def run_flask():
    logger.info(f"Iniciando servidor en puerto {PORT}")
    try:
        serve(app, host='0.0.0.0', port=PORT)
    except KeyboardInterrupt:
        logger.info("Recibida señal de interrupción")
    finally:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_manager.safe_shutdown())
        logger.info("Servidor detenido correctamente")

async def startup():
    await bot_manager.setup_webhook()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(startup())
    run_flask()