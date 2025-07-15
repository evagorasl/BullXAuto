from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Order, Profile, Coin
from bracket_config import (
    calculate_bracket, get_bracket_info, calculate_order_parameters,
    BRACKET_CONFIG, BRACKET_RANGES, TRADE_SIZES, TAKE_PROFIT_PERCENTAGES
)
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

    def calculate_bracket(self, market_cap: float) -> int:
        """Calculate bracket based on market cap using bracket_config"""
        return calculate_bracket(market_cap)
    
    def get_bracket_info(self, bracket: int) -> dict:
        """Get bracket information using bracket_config"""
        return get_bracket_info(bracket)
    
    def get_next_bracket_id(self, coin_id: int, profile_name: str) -> int:
        """Get the next available bracket_id (1-4) for a coin and profile"""
        db = self.SessionLocal()
        try:
            # Get all active orders for this coin and profile
            active_orders = db.query(Order).filter(
                Order.coin_id == coin_id,
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).all()
            
            # Get used bracket_ids
            used_bracket_ids = {order.bracket_id for order in active_orders}
            
            # Find the first available bracket_id (1-4)
            for bracket_id in range(1, 5):
                if bracket_id not in used_bracket_ids:
                    return bracket_id
            
            # If all bracket_ids are used, return None or raise an exception
            return None
        finally:
            db.close()
    
    def create_multi_order_with_bracket_config(self, address: str, strategy_number: int, 
                                             order_type: str, profile_name: str, 
                                             total_amount: float) -> dict:
        """Create multiple orders using bracket configuration automatically"""
        db = self.SessionLocal()
        try:
            # Get or create the coin
            coin = db.query(Coin).filter(Coin.address == address).first()
            if not coin:
                coin = Coin(address=address)
                db.add(coin)
                db.flush()  # Get the coin ID without committing
            
            # Calculate bracket if market_cap is available
            if coin.market_cap:
                coin.bracket = calculate_bracket(coin.market_cap)
                
                # Generate orders using bracket configuration
                order_params = calculate_order_parameters(
                    bracket=coin.bracket,
                    total_amount=total_amount,
                    current_price=coin.current_price
                )
                
                # Convert to the format expected by create_multi_order
                sub_orders = []
                for params in order_params:
                    sub_orders.append({
                        'bracket_id': params['bracket_id'],
                        'entry_price': params['entry_price'],
                        'take_profit': params['take_profit'],
                        'stop_loss': params['stop_loss'],
                        'amount': params['amount']
                    })
                
                # Use the existing create_multi_order method
                return self.create_multi_order(
                    address=address,
                    strategy_number=strategy_number,
                    order_type=order_type,
                    profile_name=profile_name,
                    sub_orders=sub_orders
                )
            else:
                raise ValueError("Cannot create orders: coin market cap is not available")
                
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def create_multi_order(self, address: str, strategy_number: int, order_type: str, 
                          profile_name: str, sub_orders: list) -> dict:
        """Create multiple orders for a coin (up to 4 orders with different bracket_ids)"""
        db = self.SessionLocal()
        try:
            # Get or create the coin
            coin = db.query(Coin).filter(Coin.address == address).first()
            if not coin:
                coin = Coin(address=address)
                db.add(coin)
                db.flush()  # Get the coin ID without committing
            
            # Update coin bracket if market_cap is available
            if coin.market_cap:
                coin.bracket = self.calculate_bracket(coin.market_cap)
            
            created_orders = []
            
            # Validate that we don't exceed 4 orders per coin per profile
            existing_active_count = db.query(Order).filter(
                Order.coin_id == coin.id,
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).count()
            
            if existing_active_count + len(sub_orders) > 4:
                raise ValueError(f"Cannot create {len(sub_orders)} orders. Maximum 4 active orders per coin per profile. Currently active: {existing_active_count}")
            
            # Create each sub-order
            for sub_order in sub_orders:
                # Check if bracket_id is already used
                existing_order = db.query(Order).filter(
                    Order.coin_id == coin.id,
                    Order.profile_name == profile_name,
                    Order.bracket_id == sub_order['bracket_id'],
                    Order.status == "ACTIVE"
                ).first()
                
                if existing_order:
                    raise ValueError(f"Bracket ID {sub_order['bracket_id']} is already in use for this coin and profile")
                
                # Create the order
                order_data = {
                    "coin_id": coin.id,
                    "strategy_number": strategy_number,
                    "order_type": order_type.upper(),
                    "bracket_id": sub_order['bracket_id'],
                    "market_cap": coin.market_cap or 0,
                    "entry_price": sub_order['entry_price'],
                    "take_profit": sub_order['take_profit'],
                    "stop_loss": sub_order['stop_loss'],
                    "amount": sub_order.get('amount'),
                    "profile_name": profile_name
                }
                
                order = Order(**order_data)
                db.add(order)
                created_orders.append(order)
            
            db.commit()
            
            # Refresh all orders to get their IDs
            for order in created_orders:
                db.refresh(order)
            
            return {
                "success": True,
                "coin": coin,
                "orders": created_orders,
                "total_orders_created": len(created_orders)
            }
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def replace_order(self, coin_id: int, bracket_id: int, profile_name: str, 
                     new_order_data: dict) -> Order:
        """Replace a completed/stopped order with a new one maintaining the same bracket_id"""
        db = self.SessionLocal()
        try:
            # Mark the old order as replaced (if it exists and is active)
            old_order = db.query(Order).filter(
                Order.coin_id == coin_id,
                Order.bracket_id == bracket_id,
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).first()
            
            if old_order:
                old_order.status = "REPLACED"
                old_order.completed_at = datetime.now()
            
            # Create new order with the same bracket_id
            new_order_data["coin_id"] = coin_id
            new_order_data["bracket_id"] = bracket_id
            new_order_data["profile_name"] = profile_name
            
            new_order = Order(**new_order_data)
            db.add(new_order)
            db.commit()
            db.refresh(new_order)
            
            return new_order
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_orders_by_bracket(self, coin_id: int, bracket_id: int, 
                             profile_name: str = None) -> List[Order]:
        """Get orders by coin and bracket_id, optionally filtered by profile"""
        db = self.SessionLocal()
        try:
            query = db.query(Order).filter(
                Order.coin_id == coin_id,
                Order.bracket_id == bracket_id
            )
            
            if profile_name:
                query = query.filter(Order.profile_name == profile_name)
            
            return query.all()
        finally:
            db.close()
    
    def get_active_orders_summary(self, profile_name: str) -> dict:
        """Get a summary of active orders grouped by coin and bracket_id"""
        db = self.SessionLocal()
        try:
            orders = db.query(Order).filter(
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).all()
            
            summary = {}
            for order in orders:
                coin_address = order.coin.address
                if coin_address not in summary:
                    summary[coin_address] = {
                        "coin": order.coin,
                        "bracket": order.coin.bracket,
                        "orders": {}
                    }
                
                summary[coin_address]["orders"][order.bracket_id] = order
            
            return summary
        finally:
            db.close()

# Global database manager instance
db_manager = DatabaseManager()
