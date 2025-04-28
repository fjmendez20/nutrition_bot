from telegram import Update
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
    handle_water_progress,  # Asegúrate de importar esta función
    handle_weight_input,
    cancel_water_reminders
)
from nutrition_plans import handle_nutrition_plan_selection, send_random_plan
from premium import handle_premium_payment
from water_reminders import handle_weight_input
from datetime import datetime
import random

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

#validacion de hora para el saludo

def obtener_saludo_por_hora():
    hora_actual = datetime.now().hour
    if 5 <= hora_actual < 12:
        return "☀️ Buenos días"
    elif 12 <= hora_actual < 19:
        return "🌤 Buenas tardes"
    else:
        return "🌙 Buenas noches"
#validacion de hora para el saludo

#array de mensajes nutricionales para el saludo
MENSAJES_NUTRICIONALES = [
    # 1. Enfoque: Hidratación (mañana/tarde/noche)
    "{saludo}, {user_name}! 💧\n\n¿Ya tomaste tu primer vaso de agua hoy? La hidratación es clave para tu metabolismo. ¡Vamos a registrar tu consumo!",
    
    # 2. Enfoque: Metas diarias
    "{saludo}, {user_name}! 🎯\n\nHoy es un gran día para cumplir tus metas nutricionales. ¿Quieres revisar tu plan de comidas?",
    
    # 3. Enfoque: Frutas/verduras
    "{saludo}, {user_name}! 🥕\n\n¿Incluiste vegetales en tu última comida? Te ayudo a planear una cena balanceada.",
    
    # 4. Enfoque: Proteínas
    "{saludo}, {user_name}! 🍛\n\nLas proteínas son esenciales para tu energía. ¿Qué fuente proteica consumiste hoy?",
    
    # 5. Enfoque: Planificación
    "{saludo}, {user_name}! 📅\n\n¿Planificaste tus comidas para hoy? Evita decisiones impulsivas. ¡Aquí estoy para ayudarte!",
    
    # 6. Enfoque: Hábitos
    "{saludo}, {user_name}! 🔍\n\nPequeños cambios = Grandes resultados. ¿Quieres evaluar tus hábitos esta semana?",
    
    # 7. Enfoque: Motivación científica
    "{saludo}, {user_name}! 📚\n\n¿Sabías que una alimentación balanceada mejora tu productividad? ¡Hagámoslo simple!",
    
    # 8. Enfoque: Cena saludable (nocturno)
    "{saludo}, {user_name}! 🌙\n\nUna cena ligera ayuda a tu digestión. ¿Necesitas ideas saludables para hoy?"
]    
#array de mensajes nutricionales para el saludo    
    
async def start(update: Update, context: CallbackContext):
    """Manejador del comando /start - Registra al usuario y muestra el menú principal"""
    try:
        logger.info(f"Nuevo start recibido de {update.effective_user.id}")
        db = get_db_session()
        user = update.effective_user
        
        logger.info(f"Buscando usuario {user.id} en DB")
        db_user = db.query(User).filter_by(telegram_id=user.id).first()
        if not db_user:
            logger.info(f"Usuario nuevo detectado, registrando...")
            db_user = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            db.add(db_user)
            db.commit()
            logger.info(f"Usuario {user.id} registrado en DB")
        
        user_name = update.effective_user.first_name or "NutriAmigo/a"
        saludo = obtener_saludo_por_hora()
        hora_actual = datetime.now().hour
        
        if hora_actual >= 19 or hora_actual < 5:
            mensaje = MENSAJES_NUTRICIONALES[7].format(saludo=saludo, user_name=user_name)
        else:
            mensaje = random.choice(MENSAJES_NUTRICIONALES[:7]).format(saludo=saludo, user_name=user_name)
        
        logger.info(f"Enviando mensaje de bienvenida a {user.id}")
        await update.message.reply_text(
            mensaje,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error en start: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text("Ocurrió un error. Por favor, inténtalo de nuevo.")

    except Exception as e:
        logger.error(f"Error en start: {e}")
        if update.message:
            await update.message.reply_text("Ocurrió un error. Por favor, inténtalo de nuevo.")

async def error_handler(update: Update, context: CallbackContext):
    """Manejador de errores"""
    logger.error(f"Error: {context.error}")
    if update.effective_message:
        await update.effective_message.reply_text(
            "¡Ups! Algo salió mal. Por favor, inténtalo de nuevo más tarde."
        )

async def main_menu(update: Update, context: CallbackContext):
    """Manejador para volver al menú principal"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_name = update.effective_user.first_name or "amigo/a"  
        mensajes = [  
            f"¡Hola <b>{user_name}</b>! 🌟\n\n"  
            "Me alegra verte por aquí otra vez. ¿En qué puedo ayudarte hoy?",  
            f"<b>{user_name}</b>, ¿listo/a para dar el siguiente paso? 💪\n\n"  
            "Elige una opción y juntos mejoraremos tus hábitos.",
            f"¡Buen momento para cuidarse, <b>{user_name}</b>! 🌱\n\n"  
            "Pequeñas decisiones hoy = Grandes resultados mañana.\n\n"  
            "¿Qué te apetece trabajar?",
            f"¡<b>{user_name}</b>! 💙\n\n"  
            "Recuerda: tu salud es una inversión, no un gasto.\n\n"  
            "¿Cómo puedo apoyarte hoy?",
            f"¡Hola de nuevo, <b>{user_name}</b>! 😊\n\n"  
            "¿Qué aspecto de tu nutrición quieres fortalecer hoy?\n\n"  
            "• 🥗 Comidas balanceadas\n"  
            "• 💧 Hidratación\n"      
        ]  
        await update.callback_query.edit_message_text(  
            text=random.choice(mensajes),  
            reply_markup=main_menu_keyboard(),  
            parse_mode="HTML"  
        )
    
    except Exception as e:
        # Si falla (porque no hay mensaje para editar), envía uno nuevo
        await update.callback_query.edit_message_text(  
            text=random.choice(mensajes),  
            reply_markup=main_menu_keyboard(),  
            parse_mode="HTML"  
        )

      


def setup_handlers(application):
    # Comandos
    application.add_handler(CommandHandler('start', start))

    # Callbacks del menú principal
    application.add_handler(CallbackQueryHandler(handle_water_reminder, pattern='^water_reminder$'))
    application.add_handler(CallbackQueryHandler(handle_nutrition_plan_selection, pattern='^nutrition_plans$'))
    application.add_handler(CallbackQueryHandler(handle_premium_payment, pattern='^premium$'))
    application.add_handler(CallbackQueryHandler(main_menu, pattern='^main_menu$'))
    
    # Callbacks de recordatorios de agua
    application.add_handler(CallbackQueryHandler(handle_water_amount, pattern='^water_amount_'))
    application.add_handler(CallbackQueryHandler(handle_water_progress, pattern='^water_progress'))
    application.add_handler(CallbackQueryHandler(cancel_water_reminders, pattern='^cancel_water_reminders$'))
    
    # Callbacks de planes nutricionales
    application.add_handler(CallbackQueryHandler(send_random_plan, pattern='^plan_'))
    
    # Manejador de errores
    application.add_error_handler(error_handler)
    
    
    # Manejo de mensajes de texto (para el peso)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^\/'),
        handle_weight_input
    ))