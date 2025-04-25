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


# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: CallbackContext):
    """Manejador del comando /start - Registra al usuario y muestra el menú principal"""
    try:
        db = get_db_session()
        user = update.effective_user
        
        # Registrar usuario en la base de datos si no existe
        db_user = db.query(User).filter_by(telegram_id=user.id).first()
        if not db_user:
            db_user = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            db.add(db_user)
            db.commit()
        
        await update.message.reply_text(
            "¡Bienvenido a tu Agente Personal de Nutrición! 👋\n\n"
            "Selecciona una opción del menú:",
            reply_markup=main_menu_keyboard()
        )
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
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Menú principal:",
        reply_markup=main_menu_keyboard()
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