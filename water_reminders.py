from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, WaterLog
from keyboards import water_amount_keyboard, water_progress_keyboard, water_reminder_keyboard
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def check_user_registered(update: Update, context: CallbackContext) -> bool:
    """Verifica si el usuario está registrado y activo"""
    user = update.effective_user
    db = None
    try:
        db = get_db_session()
        user_record = db.query(User).filter_by(telegram_id=user.id).first()
        
        if not user_record:
            logger.warning(f"Usuario no registrado intentando acceder: {user.id}")
            await update.callback_query.answer(
                "⚠️ Debes registrarte primero con /start",
                show_alert=True
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Error verificando registro: {e}")
        await update.callback_query.answer(
            "🔴 Error verificando tu registro. Intenta más tarde.",
            show_alert=True
        )
        return False
    finally:
        if db:
            db.close()


async def handle_weight_input(update: Update, context: CallbackContext):
    """Maneja la entrada del peso del usuario con validación mejorada"""
    user_id = update.message.from_user.id
    db = None
    try:
        # Validación mejorada del input
        weight_str = update.message.text.replace(',', '.').strip()
        if not weight_str.replace('.', '').isdigit():
            raise ValueError("Formato inválido")
            
        weight = float(weight_str)
        if not (30 <= weight <= 300):  # Rango más realista
            raise ValueError("Peso fuera de rango")
            
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if user:
            user.weight = weight
            user.water_goal = weight * 35  # 35ml por kg
            user.current_water = 0
            db.commit()
            
            # Limpiar estado y confirmar
            context.user_data.pop('awaiting_weight', None)
            
            await update.message.reply_text(
                f"✅ Peso registrado: {weight} kg\n"
                f"💧 Nueva meta diaria: {user.water_goal:.0f} ml",
                reply_markup=water_progress_keyboard()
            )
            
            # Reiniciar recordatorios
            await restart_water_reminders(context, user_id)
            
    except ValueError as e:
        logger.warning(f"Peso inválido: {update.message.text}")
        await update.message.reply_text(
            "⚠️ Ingresa un peso válido (30-300 kg). Ejemplo: 68.5 o 72,3",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )
    except Exception as e:
        logger.error(f"Error registrando peso: {e}")
        await update.message.reply_text("🔴 Error al registrar peso. Intenta más tarde.")
    finally:
        if db:
            db.close()
            
async def restart_water_reminders(context: CallbackContext, user_id: int):
    """Reinicia los recordatorios para un usuario"""
    try:
        if not hasattr(context, 'job_queue') or not context.job_queue:
            raise RuntimeError("JobQueue no disponible")
        
        # Cancelar jobs existentes
        for job in context.job_queue.get_jobs_by_name(f"water_reminder_{user_id}"):
            job.schedule_removal()
        
        # Programar nuevos recordatorios
        context.job_queue.run_repeating(
            callback=send_water_reminder,
            interval=timedelta(hours=1),
            first=timedelta(seconds=10),  # Primera notificación en 10 segundos
            chat_id=user_id,
            data={'user_id': user_id},
            name=f"water_reminder_{user_id}"
        )
        logger.info(f"Recordatorios reiniciados para usuario {user_id}")
        
    except Exception as e:
        logger.error(f"Error reiniciando recordatorios: {e}")
        raise


def calculate_water_goal(weight_kg: float) -> float:
    """Calcula la meta diaria de agua en ml (35ml por kg de peso)"""
    return weight_kg * 35

async def handle_water_reminder(update: Update, context: CallbackContext):
    """Manejador principal para recordatorios de agua"""
    query = update.callback_query
    await query.answer()
    
    db = None
    try:
        if not await check_user_registered(update, context):
            return
            
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
        
        if not user or not user.weight:
            context.user_data['awaiting_weight'] = True
            await query.edit_message_text(
                "⚖️ *Configuración de Peso* ⚖️\n\n"
                "Para calcular tu meta de agua, necesito saber tu peso actual.\n\n"
                "Por favor ingresa tu peso en kg (ejemplo: 68.5):\n\n"
                "⚠️ Solo el número, sin unidades o texto adicional.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ Cancelar", callback_data='main_menu')]
                ]),
                parse_mode='Markdown'
            )
            return
    
        await show_water_progress(query, user)
        
    except Exception as e:
        logger.error(f"Error en handle_water_reminder: {e}")
        await query.edit_message_text(
            "⚠️ Error al procesar tu solicitud. Intenta nuevamente.",
            reply_markup=water_reminder_keyboard()
        )
    finally:
        if db:
            db.close()

async def handle_water_progress(update: Update, context: CallbackContext):
    """Muestra el progreso actual de hidratación"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_session()
    user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
    
    if not user:
        await query.edit_message_text("❌ No se encontraron tus datos. Por favor, reinicia el bot.")
        return
    
    await show_water_progress(query, user)

async def show_water_progress(query, user: User):
    """Muestra el progreso de hidratación con visualización mejorada"""
    try:
        progress = min((user.current_water / user.water_goal) * 100, 100) if user.water_goal else 0
        progress_blocks = int(progress / 10)
        progress_bar = "🟩" * progress_blocks + "⬜" * (10 - progress_blocks)
        
        remaining = max(user.water_goal - user.current_water, 0)
        
        message = (
            "💧 *Estado de Hidratación* 💧\n\n"
            f"🚰 Consumido hoy: `{user.current_water:.0f} ml`\n"
            f"🎯 Meta diaria: `{user.water_goal:.0f} ml`\n"
            f"📊 Progreso: `{progress:.1f}%`\n"
            f"🔄 Restante: `{remaining:.0f} ml`\n\n"
            f"{progress_bar}\n\n"
        )
        
        if progress >= 100:
            message += "🎉 *¡Meta alcanzada!* ¡Buen trabajo!\n"
        
        await query.edit_message_text(
            text=message,
            reply_markup=water_progress_keyboard(),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error mostrando progreso: {e}")
        await query.edit_message_text(
            "⚠️ Error al mostrar tu progreso. Intenta más tarde.",
            reply_markup=water_progress_keyboard()
        )
    

async def handle_water_amount(update: Update, context: CallbackContext):
    """Registra la cantidad de agua consumida con límite del 100%"""
    query = update.callback_query
    await query.answer()
    
    try:
        amount = float(query.data.split('_')[-1])
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
        
        if user:
            # Calcular nuevo valor sin exceder el 100%
            new_amount = min(user.current_water + amount, user.water_goal)
            added_amount = new_amount - user.current_water
            user.current_water = new_amount
            
            db.add(WaterLog(
                user_id=user.id,
                amount=added_amount,
                timestamp=datetime.utcnow()
            ))
            db.commit()
            
            # Verificar si se alcanzó la meta
            if user.current_water >= user.water_goal:
                await query.edit_message_text(
                    "🎉 ¡Felicidades! ¡Has alcanzado tu meta diaria de hidratación! 🎉\n"
                    f"💧 Consumo total hoy: {user.current_water:.0f} ml\n\n"
                    "Los recordatorios se desactivarán hasta mañana.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Menú principal", callback_data='main_menu')]
                    ])
                )
                
                # Cancelar recordatorios
                current_jobs = context.job_queue.get_jobs_by_name(f"water_reminder_{user.telegram_id}")
                for job in current_jobs:
                    job.schedule_removal()
                
                return
            
            await show_water_progress(query, user)
            
    except Exception as e:
        logger.error(f"Error al registrar agua: {e}")
        await query.edit_message_text(
            "⚠️ No pude registrar tu consumo. Por favor, inténtalo de nuevo.",
            reply_markup=water_progress_keyboard()
        )
    finally:
        db.close()

async def start_water_reminders(context: CallbackContext, user_id: int):
    """Configura los recordatorios periódicos con manejo robusto de errores"""
    try:
        if not hasattr(context, 'job_queue') or not context.job_queue:
            logger.error("JobQueue no disponible")
            raise RuntimeError("JobQueue no configurado")
        
        # Cancelar jobs existentes para este usuario
        current_jobs = context.job_queue.get_jobs_by_name(f"water_reminder_{user_id}")
        for job in current_jobs:
            job.schedule_removal()
        
        # Programar nuevo job con intervalo configurable
        context.job_queue.run_repeating(
            callback=send_water_reminder,
            interval=3600,  # 1 hora
            first=3600,       # Primera ejecución en 5 segundos (para pruebas)
            chat_id=user_id,  # Nuevo parámetro requerido
            data={'user_id': user_id},  # Datos adicionales
            name=f"water_reminder_{user_id}"
        )
        logger.info(f"Recordatorios configurados para usuario {user_id}")
        
    except Exception as e:
        logger.error(f"Error crítico al configurar recordatorios: {e}")
        raise

async def send_water_reminder(context: CallbackContext):
    """Envía el mensaje de recordatorio con manejo de errores"""
    try:
        job = context.job
        user_id = job.data['user_id']
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if user:
            await context.bot.send_message(
                chat_id=user_id,
                text="💧 ⏰ **Recordatorio de Hidratación** ⏰ 💧\n\n"
                     "Es hora de tomar agua para mantenerte hidratado/a!\n\n"
                     "Por favor registra tu consumo usando los botones.",
                reply_markup=water_reminder_keyboard(),
                parse_mode='Markdown'
            )
            user.last_water_reminder = datetime.utcnow()
            db.commit()
    except Exception as e:
        logger.error(f"Error al enviar recordatorio: {e}")
    finally:
        db.close()
        
async def cancel_water_reminders(update: Update, context: CallbackContext):
    """Cancela los recordatorios con confirmación"""
    query = update.callback_query
    await query.answer()
    
    try:
        if hasattr(context, 'job_queue') and context.job_queue:
            jobs_removed = 0
            for job in context.job_queue.jobs():
                if job.name == f"water_reminder_{query.from_user.id}":
                    job.schedule_removal()
                    jobs_removed += 1
            
            if jobs_removed > 0:
                message = "🔕 **Recordatorios cancelados**\n\nYa no recibirás notificaciones horarias."
            else:
                message = "ℹ️ No tenías recordatorios activos para cancelar."
        else:
            message = "⚠️ No se pudo acceder al sistema de recordatorios."
        
        await query.edit_message_text(
            text=message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💧 Ver progreso", callback_data='water_progress')],
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ]),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error al cancelar recordatorios: {e}")
        await query.edit_message_text(
            "⚠️ Ocurrió un error al cancelar los recordatorios. Por favor, inténtalo de nuevo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )