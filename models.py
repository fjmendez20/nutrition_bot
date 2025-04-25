from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    """Modelo de usuario para la base de datos"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(50))
    first_name = Column(String(50))
    last_name = Column(String(50))
    weight = Column(Float)  # Peso en kg
    water_goal = Column(Float)  # Meta diaria de agua en ml
    current_water = Column(Float, default=0)  # Agua consumida hoy en ml
    is_premium = Column(Boolean, default=False)
    premium_expiry = Column(DateTime)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_water_reminder = Column(DateTime)
    language = Column(String(2), default='es')
    
    # Relaciones
    water_logs = relationship("WaterLog", back_populates="user")
    plan_downloads = relationship("PlanDownload", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class WaterLog(Base):
    """Registro de consumo de agua"""
    __tablename__ = 'water_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(Float)  # Cantidad en ml
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    user = relationship("User", back_populates="water_logs")

class PlanDownload(Base):
    """Registro de descargas de planes nutricionales"""
    __tablename__ = 'plan_downloads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    plan_type = Column(String(50))
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    user = relationship("User", back_populates="plan_downloads")

class Payment(Base):
    """Registro de pagos"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(Float)
    currency = Column(String(3), default='USD')
    payment_method = Column(String(20))
    transaction_id = Column(String(100))
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relación
    user = relationship("User", back_populates="payments")

class UserSettings(Base):
    """Configuraciones adicionales del usuario"""
    __tablename__ = 'user_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    water_reminders_enabled = Column(Boolean, default=True)
    reminder_start_time = Column(String(5), default='08:00')
    reminder_end_time = Column(String(5), default='22:00')
    notification_preference = Column(String(20), default='silent')
    
    # Relación
    user = relationship("User")