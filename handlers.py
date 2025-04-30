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
    cancel_water_reminders
)
from nutrition_plans import handle_nutrition_plan_selection, send_random_plan
from premium import handle_premium_payment
from datetime import datetime
import random
import traceback
import asyncio
import telegram


# Configuración avanzada de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración de timeout para la base de datos
DB_TIMEOUT = 10

def obtener_saludo_por_hora():
    """Devuelve un saludo según la hora del día"""
    hora_actual = datetime.now().hour
    if 5 <= hora_actual < 12:
        return "☀️ Buenos días"
    elif 12 <= hora_actual < 19:
        return "🌤 Buenas tardes"
    return "🌙 Buenas noches"

MENSAJES_NUTRICIONALES = [
    # Mensajes de bienvenida según contexto horario
    "{saludo}, {user_name}! 💧\n\n¿Ya tomaste tu primer vaso de agua hoy? La hidratación es clave para tu metabolismo. ¡Vamos a registrar tu consumo!",
    "{saludo}, {user_name}! 🎯\n\nHoy es un gran día para cumplir tus metas nutricionales. ¿Quieres revisar tu plan de comidas?",
    "{saludo}, {user_name}! 🥕\n\n¿Incluiste vegetales en tu última comida? Te ayudo a planear una cena balanceada.",
    "{saludo}, {user_name}! 🍛\n\nLas proteínas son esenciales para tu energía. ¿Qué fuente proteica consumiste hoy?",
    "{saludo}, {user_name}! 📅\n\n¿Planificaste tus comidas para hoy? Evita decisiones impulsivas. ¡Aquí estoy para ayudarte!",
    "{saludo}, {user_name}! 🔍\n\nPequeños cambios = Grandes resultados. ¿Quieres evaluar tus hábitos esta semana?",
    "{saludo}, {user_name}! 📚\n\n¿Sabías que una alimentación balanceada mejora tu productividad? ¡Hagámoslo simple!",
    "{saludo}, {user_name}! 🌙\n\nUna cena ligera ayuda a tu digestión. ¿Necesitas ideas saludables para hoy?"
]

async def start(update: Update, context: CallbackContext):
    """Manejador mejorado del comando /start"""
    try:
        user = update.effective_user
        logger.info(f"Iniciando interacción con usuario ID: {user.id}")
        
        # Registro en base de datos con manejo de timeout
        try:
            db = get_db_session()
            db_user = db.query(User).filter_by(telegram_id=user.id).first()
            
            if not db_user:
                logger.info(f"Registrando nuevo usuario: {user.id}")
                db_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db.add(db_user)
                db.commit()
        except Exception as db_error:
            logger.error(f"Error en DB: {db_error}\n{traceback.format_exc()}")
            # Continuamos aunque falle la DB
        
        # Preparar mensaje personalizado
        user_name = user.first_name or "NutriAmigo/a"
        saludo = obtener_saludo_por_hora()
        hora_actual = datetime.now().hour
        
        mensaje = (MENSAJES_NUTRICIONALES[7].format(saludo=saludo, user_name=user_name) 
                  if hora_actual >= 19 or hora_actual < 5 
                  else random.choice(MENSAJES_NUTRICIONALES[:7]).format(saludo=saludo, user_name=user_name))
        
        # Envío del mensaje con reintentos
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await update.message.reply_text(
                    mensaje,
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML"
                )
                break
            except Exception as send_error:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Intento {attempt + 1} fallido: {send_error}")
                await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error crítico en start: {e}\n{traceback.format_exc()}")
        if update.message:
            await update.message.reply_text(
                "🔴 Ocurrió un error al procesar tu solicitud. Por favor, inténtalo nuevamente."
            )

async def error_handler(update: Update, context: CallbackContext):
    """Manejador mejorado de errores globales"""
    error = context.error
    logger.error(f"Error global: {error}\n{traceback.format_exc()}")
    
    if update.callback_query:
        try:
            await update.callback_query.answer("⚠️ Error al procesar tu acción")
        except:
            pass
    
    if update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Error procesando tu solicitud. Intenta nuevamente."
        )

    if isinstance(error, telegram.error.TimedOut):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1 + attempt)  # Backoff exponencial
                await update.effective_message.reply_text(
                    f"⚠️ Timeout (intento {attempt + 1}). Reintentando..."
                )
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    await update.effective_message.reply_text(
                        "🔴 Servicio ocupado. Por favor, inténtalo más tarde."
                    )
    else:
        await update.effective_message.reply_text(
            "⚠️ Error inesperado. Nuestro equipo ha sido notificado."
        )

async def main_menu(update: Update, context: CallbackContext):
    """Manejador optimizado para el menú principal"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_name = update.effective_user.first_name or "amigo/a"
        mensajes = [  
            f"¡Hola <b>{user_name}</b>! 🌟\n\nMe alegra verte por aquí otra vez. ¿En qué puedo ayudarte hoy?",  
            f"<b>{user_name}</b>, ¿listo/a para dar el siguiente paso? 💪\n\nElige una opción y juntos mejoraremos tus hábitos.",
            f"¡Buen momento para cuidarse, <b>{user_name}</b>! 🌱\n\nPequeñas decisiones hoy = Grandes resultados mañana.",
            f"¡<b>{user_name}</b>! 💙\n\nRecuerda: tu salud es una inversión, no un gasto.",
            f"¡Hola de nuevo, <b>{user_name}</b>! 😊\n\n¿Qué aspecto de tu nutrición quieres fortalecer hoy?"
        ]
        
        try:
            await query.edit_message_text(
                text=random.choice(mensajes),
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
        except:
            # Fallback si no se puede editar el mensaje
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=random.choice(mensajes),
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Error en main_menu: {e}\n{traceback.format_exc()}")
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "❌ No pude actualizar el menú. Por favor, usa /start para reiniciar."
            )

def setup_handlers(application):
    """Configuración mejorada con logging de diagnóstico"""
    # Comandos
    application.add_handler(CommandHandler('start', start))
    
    # Handlers principales (asegúrate que los patrones coincidan con tus keyboards)
    main_handlers = [
        (CallbackQueryHandler(handle_water_reminder, pattern='^water_reminder$'), "Recordatorio de agua"),
        (CallbackQueryHandler(handle_nutrition_plan_selection, pattern='^nutrition_plans$'), "Planes nutricionales"),
        (CallbackQueryHandler(handle_premium_payment, pattern='^premium$'), "Opciones premium"),
        (CallbackQueryHandler(main_menu, pattern='^main_menu$'), "Menú principal"),
        (CallbackQueryHandler(handle_water_amount, pattern='^water_amount_'), "Cantidad de agua"),
        (CallbackQueryHandler(handle_water_progress, pattern='^water_progress'), "Progreso de agua"),
        (CallbackQueryHandler(cancel_water_reminders, pattern='^cancel_water_reminders$'), "Cancelar recordatorios"),
        (CallbackQueryHandler(send_random_plan, pattern='^plan_'), "Plan específico")
    ]
    
    for handler, description in main_handlers:
        application.add_handler(handler)
        logger.info(f"Handler registrado: {description} - Patrón: {handler.pattern}")
    
    # Mensajes de texto
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^\/'),
        handle_weight_input
    ))
    
    # Error handler
    application.add_error_handler(error_handler)
    logger.info("Todos los handlers configurados correctamente")