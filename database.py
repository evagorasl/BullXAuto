from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Order, Profile, Coin
from typing import List, Optional, Dict, Any
import os
from datetime import datetime

# Database configuration
DATABASE_URL = "sqlite:///./bullx_auto.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_profiles():
    """Initialize default profiles with API keys"""
    import secrets
    db = SessionLocal()
    try:
        # Check if profiles already exist
        existing_profiles = db.query(Profile).count()
        if existing_profiles == 0:
            # Generate secure API keys
            api_key_1 = f"bullx_{secrets.token_urlsafe(32)}"
            api_key_2 = f"bullx_{secrets.token_urlsafe(32)}"
            
            # Create default profiles
            profile1 = Profile(
                name="Saruman",
                chrome_profile_path=r"C:\Users\evago\AppData\Local\Google\Chrome\User Data\Profile Saruman",
                api_key=api_key_1
            )
            profile2 = Profile(
                name="Gandalf", 
                chrome_profile_path=r"C:\\Users\\Administrator\\AppData\\Local\\Google\\Chrome\\User Data\\Profile Gandalf",
                api_key=api_key_2
            )
            
            db.add(profile1)
            db.add(profile2)
            db.commit()
            print("Default profiles created with API keys:")
            print(f"  Saruman: {api_key_1}")
            print(f"  Gandalf: {api_key_2}")
            print("IMPORTANT: Save these API keys securely!")
    except Exception as e:
        print(f"Error initializing profiles: {e}")
        db.rollback()
    finally:
        db.close()

class DatabaseManager:
    def __init__(self):
        self.SessionLocal = SessionLocal
    
    def create_order(self, order_data: dict) -> Order:
        """Create a new order"""
        db = self.SessionLocal()
        try:
            order = Order(**order_data)
            db.add(order)
            db.commit()
            db.refresh(order)
            return order
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_active_orders(self) -> List[Order]:
        """Get all active orders"""
        db = self.SessionLocal()
        try:
            return db.query(Order).filter(Order.status == "ACTIVE").all()
        finally:
            db.close()
    
    def update_order_status(self, order_id: int, status: str) -> bool:
        """Update order status"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = status
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_profile_by_name(self, name: str) -> Optional[Profile]:
        """Get profile by name"""
        db = self.SessionLocal()
        try:
            return db.query(Profile).filter(Profile.name == name).first()
        finally:
            db.close()
    
    def update_profile_login_status(self, profile_name: str, is_logged_in: bool) -> bool:
        """Update profile login status"""
        db = self.SessionLocal()
        try:
            profile = db.query(Profile).filter(Profile.name == profile_name).first()
            if profile:
                profile.is_logged_in = is_logged_in
                if is_logged_in:
                    from datetime import datetime
                    profile.last_login = datetime.now()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_profile_by_api_key(self, api_key: str) -> Optional[Profile]:
        """Get profile by API key"""
        db = self.SessionLocal()
        try:
            return db.query(Profile).filter(
                Profile.api_key == api_key,
                Profile.is_active == True
            ).first()
        finally:
            db.close()
    
    def get_active_orders_by_profile(self, profile_name: str) -> List[Order]:
        """Get active orders for a specific profile"""
        db = self.SessionLocal()
        try:
            return db.query(Order).filter(
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).all()
        finally:
            db.close()
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validate if API key exists and is active"""
        profile = self.get_profile_by_api_key(api_key)
        return profile is not None
    
    # Coin management methods
    def get_coin_by_address(self, address: str) -> Optional[Coin]:
        """Get coin by address"""
        db = self.SessionLocal()
        try:
            return db.query(Coin).filter(Coin.address == address).first()
        finally:
            db.close()
    
    def create_or_update_coin(self, address: str, data: Dict[str, Any]) -> Coin:
        """Create a new coin or update an existing one"""
        db = self.SessionLocal()
        try:
            coin = db.query(Coin).filter(Coin.address == address).first()
            
            if coin:
                # Update existing coin
                for key, value in data.items():
                    if hasattr(coin, key) and value is not None:
                        setattr(coin, key, value)
                coin.last_updated = datetime.now()
            else:
                # Create new coin
                coin_data = {"address": address, **data}
                coin = Coin(**coin_data)
                db.add(coin)
            
            db.commit()
            db.refresh(coin)
            return coin
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_all_coins(self) -> List[Coin]:
        """Get all coins"""
        db = self.SessionLocal()
        try:
            return db.query(Coin).all()
        finally:
            db.close()
    
    # Enhanced order methods
    def create_order_with_coin(self, address: str, order_data: Dict[str, Any]) -> Order:
        """Create a new order with coin relationship"""
        db = self.SessionLocal()
        try:
            # First get or create the coin
            coin = db.query(Coin).filter(Coin.address == address).first()
            if not coin:
                coin = Coin(address=address)
                db.add(coin)
                db.flush()  # Get the coin ID without committing
            
            # Create the order linked to the coin
            order_data["coin_id"] = coin.id
            order = Order(**order_data)
            db.add(order)
            db.commit()
            db.refresh(order)
            return order
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_order_with_coin(self, order_id: int) -> Optional[Order]:
        """Get order with coin details"""
        db = self.SessionLocal()
        try:
            return db.query(Order).filter(Order.id == order_id).first()
        finally:
            db.close()
    
    def get_orders_by_coin(self, coin_id: int) -> List[Order]:
        """Get all orders for a specific coin"""
        db = self.SessionLocal()
        try:
            return db.query(Order).filter(Order.coin_id == coin_id).all()
        finally:
            db.close()
    
    def get_active_orders_by_profile_with_coins(self, profile_name: str) -> List[Order]:
        """Get active orders with coin details for a specific profile"""
        db = self.SessionLocal()
        try:
            return db.query(Order).filter(
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).all()
        finally:
            db.close()
    
    def complete_order(self, order_id: int, status: str = "COMPLETED") -> bool:
        """Mark an order as completed or stopped"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = status
                order.completed_at = datetime.now()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

# Global database manager instance
db_manager = DatabaseManager()
