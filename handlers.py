from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import logging
from database import get_db_session, User
from keyboards import (
    main_menu_keyboard,
    water_reminder_keyboard,
    water_amount_keyboard,
    water_progress_keyboard,
    nutrition_plans_keyboard,
    premium_options_keyboard
)
from water_reminders import (
    handle_water_reminder,
    handle_water_amount,
    handle_water_progress,
    handle_weight_input,
    cancel_water_reminders,
    start_water_reminders,
    handle_register_weight
)
from nutrition_plans import handle_nutrition_plan_selection, send_random_plan
from premium import handle_premium_payment
from datetime import datetime
import random
import traceback
import asyncio
import telegram

class UnregisteredUserError(Exception):
    """Excepción para usuarios no registrados"""
    pass

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración de timeout para la base de datos
DB_TIMEOUT = 10

async def send_message_with_retry(update, text, reply_markup=None, parse_mode=None, max_retries=3):
    """Envía un mensaje con mecanismo de reintento"""
    for attempt in range(max_retries):
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            else:
                await update.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            return True
        except Exception as send_error:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Intento {attempt + 1} fallido: {send_error}")
            await asyncio.sleep(1 + attempt)
    return False

def obtener_saludo_por_hora():
    """Devuelve un saludo según la hora del día"""
    hora_actual = datetime.now().hour
    if 5 <= hora_actual < 12:
        return "☀️ Buenos días"
    elif 12 <= hora_actual < 19:
        return "🌤 Buenas tardes"
    return "🌙 Buenas noches"

MENSAJES_NUTRICIONALES = [
    "{saludo}, {user_name}! 💧\n\n¿Ya tomaste tu primer vaso de agua hoy?",
    "{saludo}, {user_name}! 🎯\n\nHoy es un gran día para cumplir tus metas.",
    "{saludo}, {user_name}! 🥕\n\n¿Incluiste vegetales en tu última comida?",
    "{saludo}, {user_name}! 🍛\n\nLas proteínas son esenciales para tu energía.",
    "{saludo}, {user_name}! 📅\n\n¿Planificaste tus comidas para hoy?",
    "{saludo}, {user_name}! 🔍\n\nPequeños cambios = Grandes resultados.",
    "{saludo}, {user_name}! 📚\n\n¿Sabías que una alimentación balanceada mejora tu productividad?",
    "{saludo}, {user_name}! 🌙\n\nUna cena ligera ayuda a tu digestión."
]

async def start(update: Update, context: CallbackContext):
    """Manejador del comando /start"""
    try:
        user = update.effective_user
        logger.info(f"Iniciando interacción con usuario ID: {user.id}")
        
        db = None
        try:
            db = get_db_session()
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            if db_user:
                mensaje = f"👋 ¡Hola de nuevo, {user.first_name or 'Usuario'}!"
            else:
                db_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    registered_at=datetime.utcnow()
                )
                db.add(db_user)
                db.commit()
                mensaje = f"🎉 ¡Bienvenido/a {user.first_name or 'Nuevo Usuario'}!"
            
            saludo = obtener_saludo_por_hora()
            user_name = user.first_name or "Usuario"
            mensaje_contextual = random.choice(MENSAJES_NUTRICIONALES).format(
                saludo=saludo, user_name=user_name)
            
            await send_message_with_retry(
                update=update,
                text=f"{mensaje}\n\n{mensaje_contextual}",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )

        except Exception as db_error:
            logger.error(f"Error en DB: {db_error}\n{traceback.format_exc()}")
            await update.message.reply_text(
                "¡Hola! Estamos teniendo problemas técnicos. Intenta más tarde.",
                reply_markup=main_menu_keyboard()
            )
        finally:
            if db:
                db.close()

    except Exception as e:
        logger.error(f"Error en start: {e}\n{traceback.format_exc()}")
        if update.message:
            await update.message.reply_text("🔴 Error al procesar tu solicitud.")

async def check_user_registered(update: Update, context: CallbackContext) -> bool:
    """Verifica si el usuario está registrado"""
    user = update.effective_user
    db = None
    try:
        db = get_db_session()
        user_exists = db.query(User).filter_by(telegram_id=user.id).first() is not None
        
        if not user_exists:
            await update.callback_query.answer(
                "⚠️ Debes registrarte primero con /start",
                show_alert=True
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Error verificando registro: {e}")
        await update.callback_query.answer(
            "🔴 Error verificando tu registro.",
            show_alert=True
        )
        return False
    finally:
        if db:
            db.close()

async def main_menu(update: Update, context: CallbackContext):
    """Manejador del menú principal"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_name = update.effective_user.first_name or "amigo/a"
        mensaje = random.choice([
            f"¡Hola <b>{user_name}</b>! 🌟\n\n¿En qué puedo ayudarte hoy?",
            f"<b>{user_name}</b>, ¿listo/a para dar el siguiente paso? 💪",
            f"¡Buen momento para cuidarse, <b>{user_name}</b>! 🌱"
        ])
        
        await query.edit_message_text(
            text=mensaje,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error en main_menu: {e}")
        await query.edit_message_text("❌ Error al cargar el menú.")

async def error_handler(update: Update, context: CallbackContext):
    """Manejador de errores globales"""
    error = context.error
    logger.error(f"Error global: {error}\n{traceback.format_exc()}")
    
    try:
        if isinstance(error, UnregisteredUserError):
            await update.effective_message.reply_text(
                "🔐 Para usar esta función, primero debes registrarte con /start"
            )
        else:
            await update.effective_message.reply_text(
                "⚠️ Error procesando tu solicitud. Intenta nuevamente."
            )
    except Exception as e:
        logger.error(f"Error en el manejador de errores: {e}")

def add_registration_check(handler_func):
    """Decorador para verificación de registro"""
    async def wrapped(update: Update, context: CallbackContext):
        if not await check_user_registered(update, context):
            raise UnregisteredUserError()
        return await handler_func(update, context)
    return wrapped

def setup_handlers(application):
    """Configura todos los handlers de la aplicación"""
    # Comandos básicos
    application.add_handler(CommandHandler('start', start))
    
    # Handlers con verificación de registro
    protected_handlers = [
        ('water_reminder', handle_water_reminder),
        ('nutrition_plans', handle_nutrition_plan_selection),
        ('premium', handle_premium_payment),
        ('water_amount_', handle_water_amount),
        ('water_progress', handle_water_progress),
        ('cancel_water_reminders', cancel_water_reminders),
        ('plan_', send_random_plan)
    ]
    
    for pattern, handler in protected_handlers:
        wrapped_handler = CallbackQueryHandler(
            add_registration_check(handler),
            pattern=f'^{pattern}$'
        )
        application.add_handler(wrapped_handler)
    
    application.add_handler(CallbackQueryHandler(
        handle_register_weight,
        pattern='^register_weight$'
    ))
    
    # Handlers sin verificación de registro
    application.add_handler(CallbackQueryHandler(main_menu, pattern='^main_menu$'))
    
    # Handler para mensajes de texto (peso)
    application.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND) & filters.Regex(r'^\d+([,.]\d+)?$'),
        handle_weight_input
    ))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    logger.info("Todos los handlers configurados correctamente")