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
import sys
import asyncio

if sys.version_info >= (3, 11):
    import inspect
    if not hasattr(asyncio, 'coroutine'):
        def coroutine(f):
            return f
        asyncio.coroutine = coroutine
        
# Configuración de MEGA
MEGA_EMAIL = 'MEGA_EMAIL'  # Cambiar por tu email de MEGA
MEGA_PASSWORD = 'MEGA_PASSWORD'      # Cambiar por tu contraseña de MEGA
MEGA_FOLDER = 'nutrition_plans'      # Nombre de la carpeta principal en MEGA

# Mapeo de tipos de plan a carpetas en MEGA
PLAN_FOLDERS = {
    'weight_loss': 'weight_loss',
    'weight_gain': 'weight_gain',
    'maintenance': 'maintenance',
    'sports': 'sports',
    'metabolic': 'metabolic',
    'aesthetic': 'aesthetic'
}

# Inicializar el cliente MEGA (se conectará solo cuando sea necesario)
mega = None

def initialize_mega():
    """Inicializa la conexión con MEGA"""
    global mega
    if mega is None:
        try:
            mega = Mega()
            mega.login(MEGA_EMAIL, MEGA_PASSWORD)
            logging.info("Conexión con MEGA establecida correctamente")
        except Exception as e:
            logging.error(f"Error al conectar con MEGA: {str(e)}")
            raise

async def get_random_plan_file(plan_type):
    """Obtiene un archivo PDF aleatorio de la carpeta correspondiente en MEGA"""
    try:
        initialize_mega()
        
        folder_name = PLAN_FOLDERS.get(plan_type)
        if not folder_name:
            logging.error(f"Tipo de plan no reconocido: {plan_type}")
            return None
        
        # Buscar la carpeta principal
        root_folder = mega.find(MEGA_FOLDER)
        if not root_folder:
            logging.error(f"No se encontró la carpeta principal '{MEGA_FOLDER}' en MEGA")
            return None
        
        # Buscar la subcarpeta del plan
        plan_folder = mega.find(folder_name, root_folder[0])
        if not plan_folder:
            logging.error(f"No se encontró la carpeta '{folder_name}' en MEGA")
            return None
        
        # Obtener lista de archivos en la carpeta
        files = mega.get_files_in_node(plan_folder[0])
        pdf_files = [f for f in files.values() if f['a']['n'].lower().endswith('.pdf')]
        
        if not pdf_files:
            logging.error(f"No se encontraron PDFs en la carpeta '{folder_name}'")
            return None
        
        # Seleccionar un archivo aleatorio
        selected_file = random.choice(pdf_files)
        logging.info(f"Archivo seleccionado: {selected_file['a']['n']}")
        
        # Descargar el archivo a un directorio temporal
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, selected_file['a']['n'])
        
        mega.download_url(mega.get_upload_link(selected_file), dest_path=temp_dir)
        
        return local_path
    
    except Exception as e:
        logging.error(f"Error al obtener archivo de MEGA: {str(e)}")
        return None

async def send_random_plan(update: Update, context: CallbackContext):
    """Envía un plan nutricional aleatorio según la categoría seleccionada"""
    query = update.callback_query
    await query.answer()
    
    plan_type = query.data.split('_')[1]
    user_id = query.from_user.id
    
    logging.info(f"Buscando plan de tipo: {plan_type} para usuario: {user_id}")
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if not user:
        await query.edit_message_text("Usuario no encontrado.")
        return
    
    # Verificar límite de descargas para usuarios no premium
    if not user.is_premium:
        downloads_today = db.query(PlanDownload).filter(
            PlanDownload.user_id == user.id,
            PlanDownload.downloaded_at >= datetime.utcnow().date()
        ).count()
        
        if downloads_today >= 3:
            await query.edit_message_text(
                "⚠️ Has alcanzado tu límite de descargas gratuitas por hoy (3).\n\n"
                "Conviértete en usuario premium para descargar planes ilimitados.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 Hazte Premium", callback_data='premium')],
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
    
    try:
        # Obtener archivo aleatorio
        plan_file_path = await get_random_plan_file(plan_type)
        
        if not plan_file_path:
            logging.error(f"No se encontró archivo PDF para {plan_type}")
            await query.edit_message_text(
                "⚠️ No hay planes disponibles en esta categoría en este momento.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
        
        logging.info(f"Archivo descargado: {plan_file_path}")
        
        # Registrar descarga
        db.add(PlanDownload(
            user_id=user.id,
            plan_type=plan_type,
            downloaded_at=datetime.utcnow()
        ))
        db.commit()
        
        # Enviar documento
        with open(plan_file_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=user_id,
                document=file,
                filename=os.path.basename(plan_file_path),
                caption=f"📄 Aquí está tu plan de {plan_type.replace('_', ' ')}."
            )
        
        # Eliminar el archivo temporal después de enviarlo
        try:
            os.remove(plan_file_path)
        except Exception as e:
            logging.warning(f"No se pudo eliminar el archivo temporal: {str(e)}")
        
        # Mensajes de retorno al menú
        mensajes_retorno = [  
            f"¡Listo, {user.first_name}! 📂\n\n"  
            "Tu plan nutricional ya está en tus manos. ¿Qué tal si lo revisamos juntos más tarde?\n\n"  
            "Por ahora, ¿en qué más puedo ayudarte?",  
            f"¡Perfecto, {user.first_name}! 💡\n\n"  
            "Ahora que tienes tu plan, recuerda:\n"  
            "• Pequeños pasos son grandes logros 🚶‍♂️💨\n"  
            "• Puedes ajustarlo según cómo te sientas\n\n"  
            "¿Quieres gestionar algo más hoy?",  
            f"¡Genial, {user.first_name}! 🌟\n\n"  
            "Espero que este plan te sea útil. Si tienes dudas o quieres compartir tu progreso, ¡aquí estoy!\n\n"  
            "¿Qué hacemos ahora?"   
        ]  

        await context.bot.send_message(  
            chat_id=user_id,  
            text=random.choice(mensajes_retorno),  
            reply_markup=main_menu_keyboard(),  
            parse_mode="HTML"  
        )
        
    except Exception as e:
        logging.error(f"Error al procesar el plan: {str(e)}")
        await query.edit_message_text(
            "⚠️ Error al generar tu plan. Inténtalo más tarde.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )