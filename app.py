import sys
import asyncio

if sys.version_info >= (3, 11) and not hasattr(asyncio, 'coroutine'):
    def coroutine(f):
        return f
    asyncio.coroutine = coroutine

from telegram.ext import ApplicationBuilder
from telegram import Update
from telegram.ext import ApplicationBuilder
from telegram import Update
from config import Config
from datetime import datetime, time
from water_reminders import reset_daily_water  # Añade esto con los otros imports
from flask import Flask, request, jsonify
from telegram.request import HTTPXRequest
import threading
import time
import requests
import logging
import os

# Configuración básica de logging
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
        self.loop = asyncio.new_event_loop()
        self.request = HTTPXRequest(
            connection_pool_size=10,
            read_timeout=20.0,
            write_timeout=20.0,
            connect_timeout=20.0,
            pool_timeout=30.0
        )
        self._init_lock = threading.Lock()
        self._async_init_lock = None
        self._start_background_loop()
        self.initialize()
    
    async def _setup_daily_reset(self):
        """Configura el job de reinicio diario"""
        try:
            # Verifica si ya existe un job de reinicio
            if not any(job.name == "daily_reset" for job in self.application.job_queue.jobs()):
                # Configura para ejecutarse diariamente a las 00:00 (medianoche)
                self.application.job_queue.run_daily(
                    callback=reset_daily_water,
                    time=time(0, 0),  # 00:00 (medianoche)
                    days=(0, 1, 2, 3, 4, 5, 6),  # Todos los días de la semana
                    name="daily_reset"
                )
                logger.info("Job de reinicio diario configurado correctamente")
        except Exception as e:
            logger.error(f"Error configurando el reinicio diario: {e}")

    def _start_background_loop(self):
        def run_loop():
            asyncio.set_event_loop(self.loop)
            # Inicializamos el lock asíncrono dentro del event loop
            self.loop.run_until_complete(self._init_async_lock())
            self.loop.run_forever()
            
        threading.Thread(
            target=run_loop,
            daemon=True,
            name='BotManagerLoop'
        ).start()

    async def _init_async_lock(self):
        """Inicializa el lock asíncrono dentro del event loop"""
        self._async_init_lock = asyncio.Lock()

    async def _initialize(self):
        with self._init_lock:
            if self.application is None:
                if self._async_init_lock is None:
                    await asyncio.sleep(0.1)
                
                async with self._async_init_lock:
                    self.application = (
                        ApplicationBuilder()
                        .token(Config.TELEGRAM_TOKEN)
                        .arbitrary_callback_data(False)
                        .request(self.request)
                        .build()
                    )
                    
                    from handlers import setup_handlers
                    setup_handlers(self.application)
                    
                    await self.application.initialize()
                    await self.application.start()
                    
                    # Configurar el reinicio diario después de iniciar
                    await self._setup_daily_reset()
                    
                    logger.info("Bot inicializado correctamente")

    def initialize(self):
        future = asyncio.run_coroutine_threadsafe(
            self._initialize(),
            self.loop
        )
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error inicializando el bot: {str(e)}")
            raise

    async def _setup_webhook(self):
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        await self.application.bot.delete_webhook()
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=Config.WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query"],
            max_connections=20
        )
        logger.info(f"Webhook configurado en: {webhook_url}")

    def setup_webhook(self):
        future = asyncio.run_coroutine_threadsafe(
            self._setup_webhook(),
            self.loop
        )
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error configurando webhook: {str(e)}")
            raise

    async def _process_update(self, update_data):
        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)
        return True

    def process_update(self, update_data):
        future = asyncio.run_coroutine_threadsafe(
            self._process_update(update_data),
            self.loop
        )
        try:
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}")
            return False

def keep_alive():
    """Función para mantener activa la instancia con pings periódicos"""
    while True:
        try:
            if hasattr(Config, 'RENDER_DOMAIN') and Config.RENDER_DOMAIN:
                url = f'https://{Config.RENDER_DOMAIN}/health'
                response = requests.get(url, timeout=40)
                logger.info(f"Keep-alive ping. Status: {response.status_code}")
            else:
                logger.warning("RENDER_DOMAIN no configurado")
        except Exception as e:
            logger.error(f"Error en keep-alive: {str(e)}")
        time.sleep(240)

# Inicialización del bot
try:
    bot_manager = BotManager()
    bot_manager.setup_webhook()
except Exception as e:
    logger.critical(f"Fallo al iniciar el bot: {str(e)}")
    raise

# Endpoints Flask
@app.route('/')
def home():
    return "¡Bot activo! Webhook configurado en /webhook"

@app.post('/webhook')
def webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
    
    try:
        update_data = request.get_json()
        logger.info(f"Update recibido (type: {update_data.get('update_id')})")
        success = bot_manager.process_update(update_data)
        return "ok" if success else "error", 200
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return "server error", 500

@app.get('/health')
def health_check():
    """Endpoint para verificaciones de salud y keep-alive"""
    return jsonify({
        "status": "healthy",
        "bot": "running" if bot_manager.application else "starting",
        "timestamp": time.time()
    }), 200

def run_server():
    """Inicia el servidor web"""
    from waitress import serve
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT, threads=4)

if __name__ == '__main__':
    # Inicia el thread de keep-alive
    threading.Thread(
        target=keep_alive,
        daemon=True,
        name='KeepAliveThread'
    ).start()
    
    # Inicia el servidor
    run_server()