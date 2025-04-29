from telegram.ext import ApplicationBuilder
from telegram import Update, User, Chat, Message
from config import Config
import logging
import os
from flask import Flask, request, jsonify
from waitress import serve
import asyncio
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from flask_sqlalchemy import SQLAlchemy

# Configuración avanzada de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración de la aplicación Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
PORT = int(os.environ.get('PORT', 10000))

# Base de datos
db = SQLAlchemy(app)

# Modelo de ejemplo para almacenamiento de datos
class UserInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    command = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime)

# Pool de threads para manejo concurrente
executor = ThreadPoolExecutor(max_workers=4)

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
        """Configura el webhook con reintentos"""
        if not self.initialized:
            self.initialize()
            
        webhook_url = f"https://{Config.RENDER_DOMAIN}/webhook"
        
        for attempt in range(3):  # 3 intentos
            try:
                await self.application.initialize()
                await self.application.start()
                await self.application.bot.set_webhook(
                    url=webhook_url,
                    secret_token=Config.WEBHOOK_SECRET,
                    drop_pending_updates=True,
                    allowed_updates=["message", "callback_query"]
                )
                logger.info(f"Webhook configurado en: {webhook_url}")
                return True
            except Exception as e:
                logger.error(f"Intento {attempt + 1} fallido: {str(e)}")
                await asyncio.sleep(2)
        
        logger.error("No se pudo configurar el webhook después de 3 intentos")
        return False

    async def process_update(self, update_data):
        """Procesa una actualización con manejo robusto de errores"""
        try:
            if not self.initialized:
                self.initialize()
                await self.application.initialize()
                await self.application.start()
            
            # Validación y normalización de datos
            if 'message' in update_data:
                msg = update_data['message']
                if 'from' in msg and 'is_bot' not in msg['from']:
                    msg['from']['is_bot'] = False
                
                if 'chat' not in msg and 'from' in msg:
                    msg['chat'] = msg['from']
            
            update = Update.de_json(update_data, self.application.bot)
            
            if update is None:
                logger.error("Update inválido recibido")
                return False
                
            # Registrar interacción en la base de datos
            if update.message:
                self.record_interaction(
                    user_id=update.message.from_user.id,
                    command=update.message.text or "N/A"
                )
            
            await self.application.process_update(update)
            return True
            
        except Exception as e:
            logger.error(f"Error procesando update: {str(e)}")
            logger.error(f"Datos del update: {update_data}")
            return False

    def record_interaction(self, user_id, command):
        """Registra interacciones en la base de datos (ejecutado en thread separado)"""
        try:
            interaction = UserInteraction(
                user_id=user_id,
                command=command[:50],  # Limitar longitud
                timestamp=datetime.now()
            )
            db.session.add(interaction)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error registrando interacción: {str(e)}")

# Instancia global del bot
bot_manager = BotManager()

@app.route('/')
def home():
    return "¡Bot activo! Endpoints: /webhook, /webhook_status, /stats"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para actualizaciones de Telegram con rate limiting básico"""
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != Config.WEBHOOK_SECRET:
        logger.warning("Intento de acceso no autorizado al webhook")
        return "Unauthorized", 401
    
    try:
        update_data = request.get_json()
        logger.debug(f"Update recibido: {update_data}")
        
        # Añadir a la cola para procesamiento asíncrono
        update_queue.put(update_data)
        return "ok", 200
        
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/webhook_status', methods=['GET'])
async def webhook_status():
    """Endpoint para verificar el estado del webhook"""
    try:
        info = await bot_manager.application.bot.get_webhook_info()
        return jsonify({
            'url': info.url,
            'pending_updates': info.pending_update_count,
            'last_error_date': info.last_error_date,
            'last_error_message': info.last_error_message,
            'active': True if info.url else False
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint para obtener estadísticas básicas"""
    try:
        user_count = db.session.query(UserInteraction.user_id).distinct().count()
        popular_commands = db.session.query(
            UserInteraction.command,
            db.func.count(UserInteraction.command)
        ).group_by(UserInteraction.command).order_by(db.func.count(UserInteraction.command).desc()).limit(5).all()
        
        return jsonify({
            "total_users": user_count,
            "popular_commands": [{"command": cmd, "count": cnt} for cmd, cnt in popular_commands]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

async def process_updates():
    """Procesa updates de la cola de manera asíncrona"""
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
    with app.app_context():
        db.create_all()  # Crear tablas si no existen
    
    logger.info(f"Iniciando servidor en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Inicia el bot en un hilo separado
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Inicia Flask en el hilo principal
    run_flask()