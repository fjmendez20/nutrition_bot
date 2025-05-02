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
from config import Config


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
            mega.login(Config.MEGA_EMAIL, Config.MEGA_PASSWORD)
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
            error_msg = f"Tipo de plan no reconocido: {plan_type}"
            logging.error(error_msg)
            return None
        
        # Buscar carpetas en MEGA
        root_folder = mega.find(MEGA_FOLDER)
        if not root_folder:
            error_msg = f"Carpeta principal '{MEGA_FOLDER}' no encontrada en MEGA"
            logging.error(error_msg)
            return None
        
        logging.info(f"Buscando carpeta '{folder_name}' dentro de '{MEGA_FOLDER}'")
        plan_folder = mega.find(folder_name, root_folder[0])
        if not plan_folder:
            error_msg = f"Carpeta '{folder_name}' no encontrada en '{MEGA_FOLDER}'"
            logging.error(error_msg)
            return None
        
        # Filtrar archivos PDF
        logging.info(f"Obteniendo archivos de la carpeta '{folder_name}'")
        files = mega.get_files_in_node(plan_folder[0])
        if not files:
            error_msg = f"No se encontraron archivos en '{folder_name}'"
            logging.error(error_msg)
            return None
        
        pdf_files = [f for f in files.values() if f['a']['n'].lower().endswith('.pdf')]
        
        if not pdf_files:
            error_msg = f"No hay PDFs en '{folder_name}' (se encontraron {len(files)} archivos)"
            logging.error(error_msg)
            return None
        
        # Descargar archivo temporal
        selected_file = random.choice(pdf_files)
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, selected_file['a']['n'])
        
        logging.info(f"Descargando archivo: {selected_file['a']['n']}")
        download_url = mega.get_upload_link(selected_file)
        if not download_url:
            error_msg = "No se pudo obtener URL de descarga"
            logging.error(error_msg)
            return None
            
        mega.download_url(download_url, dest_path=temp_dir)
        
        if not os.path.exists(local_path):
            error_msg = f"El archivo no se descargó correctamente en {local_path}"
            logging.error(error_msg)
            return None
            
        return local_path
    
    except Exception as e:
        error_msg = f"Error al obtener archivo: {str(e)} - Tipo: {type(e).__name__}"
        logging.error(error_msg, exc_info=True)
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