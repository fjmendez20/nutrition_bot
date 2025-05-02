import random
import os
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, PlanDownload
from keyboards import nutrition_plans_keyboard, main_menu_keyboard
from datetime import datetime
from mega import Mega
import tempfile
import logging
from config import config


MEGA_FOLDER = 'nutrition_plans'

# Mapeo de tipos de plan a carpetas
PLAN_FOLDERS = {
    'weight_loss': 'weight_loss',
    'weight_gain': 'weight_gain',
    'maintenance': 'maintenance',
    'sports': 'sports',
    'metabolic': 'metabolic',
    'aesthetic': 'aesthetic'
}

# Cliente MEGA (singleton)
mega = None

def initialize_mega():
    """Inicializa la conexión con MEGA"""
    global mega
    if mega is None:
        try:
            mega = Mega()
            mega.login(config.MEGA_EMAIL, config.MEGA_PASSWORD)
            logging.info("Conexión con MEGA establecida")
        except Exception as e:
            logging.error(f"Error al conectar con MEGA: {str(e)}")
            raise

async def handle_nutrition_plan_selection(update: Update, context: CallbackContext):
    """Muestra el menú de selección de planes nutricionales"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📚 Selecciona el tipo de plan nutricional que deseas:\n\n"
        "Cada plan está diseñado por expertos en nutrición para ayudarte a alcanzar tus metas.",
        reply_markup=nutrition_plans_keyboard()
    )

async def get_random_plan_file(plan_type):
    """Obtiene un archivo PDF aleatorio de MEGA"""
    try:
        initialize_mega()
        
        folder_name = PLAN_FOLDERS.get(plan_type)
        if not folder_name:
            logging.error(f"Tipo de plan no reconocido: {plan_type}")
            return None
        
        # Buscar carpetas en MEGA
        root_folder = mega.find(MEGA_FOLDER)
        if not root_folder:
            logging.error(f"Carpeta principal '{MEGA_FOLDER}' no encontrada")
            return None
        
        plan_folder = mega.find(folder_name, root_folder[0])
        if not plan_folder:
            logging.error(f"Carpeta '{folder_name}' no encontrada")
            return None
        
        # Filtrar archivos PDF
        files = mega.get_files_in_node(plan_folder[0])
        pdf_files = [f for f in files.values() if f['a']['n'].lower().endswith('.pdf')]
        
        if not pdf_files:
            logging.error(f"No hay PDFs en '{folder_name}'")
            return None
        
        # Descargar archivo temporal
        selected_file = random.choice(pdf_files)
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, selected_file['a']['n'])
        mega.download_url(mega.get_upload_link(selected_file), dest_path=temp_dir)
        
        return local_path
    
    except Exception as e:
        logging.error(f"Error al obtener archivo: {str(e)}")
        return None

async def send_random_plan(update: Update, context: CallbackContext):
    """Envía un plan nutricional aleatorio"""
    query = update.callback_query
    await query.answer()
    
    plan_type = query.data.split('_')[1]
    user_id = query.from_user.id
    logging.info(f"Buscando plan {plan_type} para usuario {user_id}")
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if not user:
        await query.edit_message_text("Usuario no encontrado.")
        return
    
    # Límite de descargas para no premium
    if not user.is_premium:
        downloads_today = db.query(PlanDownload).filter(
            PlanDownload.user_id == user.id,
            PlanDownload.downloaded_at >= datetime.utcnow().date()
        ).count()
        
        if downloads_today >= 3:
            await query.edit_message_text(
                "⚠️ Límite de descargas alcanzado (3/día).\n"
                "Hazte Premium para descargas ilimitadas.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 Hazte Premium", callback_data='premium')],
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
    
    try:
        plan_file_path = await get_random_plan_file(plan_type)
        
        if not plan_file_path:
            await query.edit_message_text(
                "⚠️ No hay planes disponibles ahora.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
        
        # Registrar y enviar
        db.add(PlanDownload(
            user_id=user.id,
            plan_type=plan_type,
            downloaded_at=datetime.utcnow()
        ))
        db.commit()
        
        with open(plan_file_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=user_id,
                document=file,
                filename=os.path.basename(plan_file_path),
                caption=f"📄 Plan de {plan_type.replace('_', ' ')}"
            )
        
        # Limpiar temporal
        try:
            os.remove(plan_file_path)
        except Exception as e:
            logging.warning(f"Error eliminando temporal: {str(e)}")
        
        # Mensaje final
        await context.bot.send_message(  
            chat_id=user_id,  
            text=random.choice([  
                f"¡Listo, {user.first_name}! 📂\n\n¿En qué más puedo ayudarte?",  
                f"¡Perfecto, {user.first_name}! 💡\n\n¿Qué hacemos ahora?",  
                f"¡Genial, {user.first_name}! 🌟\n\n¿Necesitas algo más?"   
            ]),  
            reply_markup=main_menu_keyboard(),  
            parse_mode="HTML"  
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await query.edit_message_text(
            "⚠️ Error al generar tu plan. Inténtalo más tarde.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )

# Exportación explícita para evitar errores de importación
__all__ = ['handle_nutrition_plan_selection', 'send_random_plan']