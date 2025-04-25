from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User
import logging
import pytz

# Configuración de logging
logger = logging.getLogger(__name__)

def get_user(telegram_id: int) -> Optional[User]:
    """Obtiene un usuario de la base de datos"""
    db = get_db_session()
    try:
        return db.query(User).filter_by(telegram_id=telegram_id).first()
    except Exception as e:
        logger.error(f"Error al obtener usuario: {e}")
        return None
    finally:
        db.close()

def calculate_water_goal(weight_kg: float) -> float:
    """Calcula la meta diaria de agua en ml"""
    return weight_kg * 35  # 35 ml por kg de peso

def format_water_progress(current: float, goal: float) -> str:
    """Formatea el progreso de hidratación para mostrarlo al usuario"""
    if goal == 0:
        return "0%"
    
    progress = (current / goal) * 100
    progress_bar = "🟩" * int(progress / 10) + "⬜" * (10 - int(progress / 10))
    return f"{progress:.1f}%\n{progress_bar}"

def validate_time_format(time_str: str) -> bool:
    """Valida que una cadena esté en formato HH:MM"""
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False

def localize_time(utc_time: datetime, timezone_str: str = 'America/Mexico_City') -> datetime:
    """Convierte UTC a la zona horaria local"""
    try:
        tz = pytz.timezone(timezone_str)
        return utc_time.astimezone(tz)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Zona horaria {timezone_str} no reconocida, usando UTC")
        return utc_time

def format_datetime(dt: datetime, include_time: bool = True) -> str:
    """Formatea una fecha para mostrarla al usuario"""
    if not dt:
        return "Nunca"
    
    localized = localize_time(dt)
    if include_time:
        return localized.strftime("%d/%m/%Y %H:%M")
    return localized.strftime("%d/%m/%Y")

def create_pagination_keyboard(
    current_page: int, 
    total_pages: int, 
    prefix: str,
    additional_buttons: list = None
) -> InlineKeyboardMarkup:
    """Crea un teclado de paginación"""
    buttons = []
    
    # Botones de navegación
    if current_page > 1:
        buttons.append(InlineKeyboardButton("⬅ Anterior", callback_data=f"{prefix}_{current_page-1}"))
    
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton("Siguiente ➡", callback_data=f"{prefix}_{current_page+1}"))
    
    # Botones adicionales si se proporcionan
    if additional_buttons:
        buttons.extend(additional_buttons)
    
    return InlineKeyboardMarkup([buttons])

def error_handler(update: Update, context: CallbackContext):
    """Manejador centralizado de errores"""
    error = context.error
    logger.error(f"Error durante la actualización {update}: {error}")
    
    if update.effective_message:
        update.effective_message.reply_text(
            "⚠️ Ocurrió un error inesperado. Por favor, inténtalo de nuevo más tarde."
        )

def is_user_premium(user_id: int) -> bool:
    """Verifica si un usuario tiene suscripción premium activa"""
    db = get_db_session()
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            return False
            
        return user.is_premium and (
            not user.premium_expiry or 
            user.premium_expiry > datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Error al verificar premium: {e}")
        return False
    finally:
        db.close()

def get_user_language(user_id: int, default: str = 'es') -> str:
    """Obtiene el idioma preferido del usuario"""
    user = get_user(user_id)
    return user.language if user and user.language else default

def build_menu(buttons: list, n_cols: int = 2, header_buttons=None, footer_buttons=None) -> list:
    """Construye un menú de botones organizados en columnas"""
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    
    if header_buttons:
        menu.insert(0, header_buttons if isinstance(header_buttons, list) else [header_buttons])
    
    if footer_buttons:
        menu.append(footer_buttons if isinstance(footer_buttons, list) else [footer_buttons])
    
    return menu