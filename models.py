from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

Base = declarative_base()

class Coin(Base):
    __tablename__ = "coins"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)  # Coin name (may be null initially)
    address = Column(String, unique=True, nullable=False, index=True)
    url = Column(String, nullable=True)  # URL to the coin on BullX
    market_cap = Column(Float, nullable=True)  # Current market cap
    current_price = Column(Float, nullable=True)  # Current price
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    orders = relationship("Order", back_populates="coin")
    
    def __repr__(self):
        return f"<Coin(name='{self.name}', address='{self.address}', market_cap={self.market_cap})>"

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    strategy_number = Column(Integer, nullable=False)
    order_type = Column(String, nullable=False)  # BUY or SELL
    market_cap = Column(Float, nullable=False)  # Market cap at time of order
    entry_price = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    amount = Column(Float, nullable=True)  # Amount of the order (optional)
    status = Column(String, default="ACTIVE")  # ACTIVE, COMPLETED, STOPPED
    profile_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)  # When the order was completed/stopped
    order_id_bullx = Column(String, nullable=True)  # BullX order ID if available
    
    # Relationships
    coin = relationship("Coin", back_populates="orders")
    
    def __repr__(self):
        return f"<Order(id={self.id}, coin_id={self.coin_id}, type='{self.order_type}', status='{self.status}')>"

class Profile(Base):
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    chrome_profile_path = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False, index=True)
    is_logged_in = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

# Pydantic models for API requests/responses
class LoginRequest(BaseModel):
    pass  # No fields needed - profile determined by API key

class SearchRequest(BaseModel):
    address: str

class StrategyRequest(BaseModel):
    strategy_number: int
    address: str
    order_type: str  # BUY or SELL
    entry_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None

class ProfileResponse(BaseModel):
    name: str
    is_logged_in: bool
    last_login: Optional[datetime]
    is_active: bool
    
    class Config:
        from_attributes = True

class CoinResponse(BaseModel):
    id: int
    name: Optional[str]
    address: str
    url: Optional[str]
    market_cap: Optional[float]
    current_price: Optional[float]
    last_updated: datetime
    
    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    coin_id: int
    strategy_number: int
    order_type: str
    market_cap: float
    entry_price: float
    take_profit: float
    stop_loss: float
    amount: Optional[float]
    status: str
    profile_name: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class OrderDetailResponse(BaseModel):
    id: int
    coin: CoinResponse
    strategy_number: int
    order_type: str
    market_cap: float
    entry_price: float
    take_profit: float
    stop_loss: float
    amount: Optional[float]
    status: str
    profile_name: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
