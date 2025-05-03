from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from database import get_db_session, User, WaterLog
from keyboards import water_amount_keyboard, water_progress_keyboard, water_reminder_keyboard
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def check_user_registered(update: Update, context: CallbackContext) -> bool:
    """Verifica si el usuario está registrado antes de ejecutar acciones"""
    user = update.effective_user
    db = get_db_session()
    try:
        user_exists = db.query(User).filter_by(telegram_id=user.id).first() is not None
        
        if not user_exists:
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
        db.close()


async def handle_weight_input(update: Update, context: CallbackContext):
    """Maneja la entrada del peso del usuario"""
    user_id = update.message.from_user.id
    db = None
    try:
        weight = float(update.message.text.replace(',', '.'))  # Acepta tanto . como ,
        if weight <= 0 or weight > 300:
            raise ValueError("Peso inválido")
            
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if user:
            user.weight = weight
            user.water_goal = calculate_water_goal(weight)
            user.current_water = 0  # Resetear el contador diario
            db.commit()
            
            # Eliminar el estado awaiting_weight
            if 'awaiting_weight' in context.user_data:
                del context.user_data['awaiting_weight']
            
            await update.message.reply_text(
                f"✅ Peso registrado correctamente: {weight} kg\n"
                f"📌 Tu meta diaria de agua es: {user.water_goal:.0f} ml",
                reply_markup=water_progress_keyboard()
            )
            
            # Iniciar recordatorios con manejo de errores
            try:
                await start_water_reminders(context, user_id)
            except Exception as e:
                logger.error(f"Error al iniciar recordatorios: {e}")
                await update.message.reply_text(
                    "⚠️ Se configuró tu peso pero hubo un error con los recordatorios. "
                    "Por favor, vuelve a intentarlo más tarde.",
                    reply_markup=water_progress_keyboard()
                )
    except ValueError as e:
        logger.warning(f"Peso inválido ingresado: {update.message.text}")
        await update.message.reply_text(
            "⚠️ Por favor ingresa un peso válido entre 1 y 300 kg (ejemplo: 68.5 o 72,3)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
            ])
        )
    finally:
        if db:
            db.close()

def calculate_water_goal(weight_kg: float) -> float:
    """Calcula la meta diaria de agua en ml (35ml por kg de peso)"""
    return weight_kg * 35

async def handle_water_reminder(update: Update, context: CallbackContext):
    """Manejador de recordatorios de agua con verificación de registro"""
    query = update.callback_query
    await query.answer()
    
    db = None
    try:
        # Verificar registro primero
        if not await check_user_registered(update, context):
            return
            
        db = get_db_session()
        user = db.query(User).filter_by(telegram_id=query.from_user.id).first()
        
        if not user or not user.weight:
            context.user_data['awaiting_weight'] = True
            await query.edit_message_text(
                "💧 Para configurar recordatorios de hidratación:\n\n"
                "Por favor ingresa tu peso actual en kilogramos (ejemplo: 65.5):\n\n"
                "⚠️ Envía solo el número, sin unidades.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menú principal", callback_data='main_menu')]
                ])
            )
            return
    
        # Mostrar directamente el progreso con el teclado de registrar agua
        await show_water_progress(query, user)
    except Exception as e:
        logger.error(f"Error en handle_water_reminder: {e}")
        await query.edit_message_text(
            "⚠️ Ocurrió un error al configurar recordatorios. Intenta nuevamente."
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

async def show_water_progress(query, user):
    """Muestra el progreso de hidratación con límite del 100%"""
    try:
        progress = min((user.current_water / user.water_goal) * 100, 100) if user.water_goal else 0
        progress_bar = "🟩" * int(progress / 10) + "⬜" * (10 - int(progress / 10))
        
        message = (
            f"💧 **Progreso de Hidratación** 💧\n\n"
            f"🚰 Consumo actual: `{user.current_water:.0f} ml`\n"
            f"🎯 Meta diaria: `{user.water_goal:.0f} ml`\n"
            f"📊 Progreso: `{progress:.1f}%`\n\n"
            f"{progress_bar}\n\n"
        )
        
        if progress >= 100:
            message += "✅ ¡Meta cumplida! ¡Buen trabajo!"
        
        await query.edit_message_text(
            text=message,
            reply_markup=water_progress_keyboard(),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error al mostrar progreso: {e}")
        await query.edit_message_text(
            "⚠️ Ocurrió un error al mostrar tu progreso. Por favor, inténtalo de nuevo.",
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