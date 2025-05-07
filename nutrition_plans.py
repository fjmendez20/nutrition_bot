import random
import os
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, PlanDownload
from keyboards import nutrition_plans_keyboard, main_menu_keyboard
from datetime import datetime
import tempfile
import logging
from config import Config

# Mapeo de tipos de plan a carpetas (debe coincidir con los nombres de tus carpetas en categorias/)
PLAN_FOLDERS = {
    'weight_loss': 'Pérdida_de_Peso',
    'weight_gain': 'Aumento_Muscular',
    'maintenance': 'Mantenimiento',
    'sports': 'Rendimiento_Deportivo',
    'metabolic': 'Salud_Metabólica',
    'aesthetic': 'Objetivos_Estéticos'
}

# Ruta a los archivos de IDs (debe estar en static/ids)
IDS_FOLDER = os.path.join('static', 'ids')

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
    """Obtiene un file_id aleatorio de los archivos de IDs"""
    try:
        folder_name = PLAN_FOLDERS.get(plan_type)
        if not folder_name:
            logging.error(f"Tipo de plan no reconocido: {plan_type}")
            return None
        
        # Ruta al archivo de IDs para esta categoría
        ids_file = os.path.join(IDS_FOLDER, f"{folder_name}.txt")
        
        if not os.path.exists(ids_file):
            logging.error(f"Archivo de IDs no encontrado: {ids_file}")
            return None
        
        # Cargar los IDs desde el archivo
        with open(ids_file, 'r') as f:
            ids_data = json.load(f)
        
        if not ids_data:
            logging.error(f"No hay IDs disponibles en {ids_file}")
            return None
        
        # Seleccionar un archivo aleatorio
        file_name, file_id = random.choice(list(ids_data.items()))
        
        return {
            'file_id': file_id,
            'file_name': file_name
        }
    
    except Exception as e:
        logging.error(f"Error al obtener archivo: {str(e)}", exc_info=True)
        return None

async def send_random_plan(update: Update, context: CallbackContext):
    """Envía un plan nutricional aleatorio usando los file_ids de Telegram"""
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
        plan_data = await get_random_plan_file(plan_type)
        
        if not plan_data:
            await query.edit_message_text(
                "⚠️ No hay planes disponibles ahora.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
        
        # Registrar descarga
        db.add(PlanDownload(
            user_id=user.id,
            plan_type=plan_type,
            downloaded_at=datetime.utcnow()
        ))
        db.commit()
        
        # Enviar documento usando el file_id
        await context.bot.send_document(
            chat_id=user_id,
            document=plan_data['file_id'],
            filename=plan_data['file_name'],
            caption=f"📄 Plan de {plan_type.replace('_', ' ')}"
        )
        
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