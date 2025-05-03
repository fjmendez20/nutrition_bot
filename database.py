import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config
from datetime import datetime

DATABASE_URL = os.getenv('DATABASE_URL')


Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    weight = Column(Float)
    water_goal = Column(Float)  # en ml
    current_water = Column(Float, default=0)  # en ml
    is_premium = Column(Boolean, default=False)
    premium_expiry = Column(DateTime)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_water_reminder = Column(DateTime)

class WaterLog(Base):
    __tablename__ = 'water_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float)  # en ml
    timestamp = Column(DateTime, default=datetime.utcnow)

class PlanDownload(Base):
    __tablename__ = 'plan_downloads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    plan_type = Column(String)
    downloaded_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float)
    currency = Column(String, default='USD')
    payment_method = Column(String)
    transaction_id = Column(String)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

# Configuración de la base de datos
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_db_session():
    return Session()