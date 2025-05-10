from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from zoneinfo import ZoneInfo  # Para Python 3.9+

# Configuración de zona horaria UTC-4
UTC_4 = ZoneInfo("America/Puerto_Rico")

def utcnow():
    """Función helper para obtener datetime actual en UTC-4"""
    return datetime.now(UTC_4)

Base = declarative_base()

class User(Base):
    """Modelo de usuario con todas las relaciones"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(50), nullable=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    weight = Column(Float)  # Peso en kg
    water_goal = Column(Float)  # Meta diaria de agua en ml
    current_water = Column(Float, default=0)  # Agua consumida hoy en ml
    is_premium = Column(Boolean, default=False)
    premium_expiry = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=utcnow)
    last_water_reminder = Column(DateTime, nullable=True)
    language = Column(String(2), default='es')  # Código de idioma (ej: 'es', 'en')
    
    # Relaciones
    water_logs = relationship("WaterLog", back_populates="user", cascade="all, delete-orphan")
    plan_downloads = relationship("PlanDownload", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", uselist=False, back_populates="user", cascade="all, delete-orphan")

class WaterLog(Base):
    """Registro detallado de consumo de agua"""
    __tablename__ = 'water_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)  # Cantidad en ml
    timestamp = Column(DateTime, default=utcnow, index=True)
    is_daily_reset = Column(Boolean, default=False)  # Indica si es un registro de reset
    
    # Relación
    user = relationship("User", back_populates="water_logs")

class PlanDownload(Base):
    """Registro de descargas de planes nutricionales"""
    __tablename__ = 'plan_downloads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    plan_type = Column(String(50), nullable=False)  # Ej: 'keto', 'vegetariano', etc.
    downloaded_at = Column(DateTime, default=utcnow)
    
    # Relación
    user = relationship("User", back_populates="plan_downloads")

class Payment(Base):
    """Registro de transacciones de pago"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default='USD')  # Código ISO 4217
    payment_method = Column(String(20))  # Ej: 'stripe', 'paypal', etc.
    transaction_id = Column(String(100), unique=True)
    status = Column(String(20), default='pending')  # Ej: 'pending', 'completed', 'failed'
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relación
    user = relationship("User", back_populates="payments")

class UserSettings(Base):
    """Configuraciones personalizadas del usuario"""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    water_reminders_enabled = Column(Boolean, default=True)
    reminder_start_time = Column(String(5), default='08:00')  # Formato HH:MM (UTC-4)
    reminder_end_time = Column(String(5), default='22:00')    # Formato HH:MM (UTC-4)
    reminder_interval = Column(Integer, default=60)  # Intervalo en minutos
    notification_preference = Column(String(20), default='silent')  # Ej: 'sound', 'vibrate', 'silent'
    
    # Relación
    user = relationship("User", back_populates="settings")