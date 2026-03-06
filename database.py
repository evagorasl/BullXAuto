from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Order, Profile, Coin, QueuedExecution
from bracket_config import (
    calculate_bracket, get_bracket_info, calculate_order_parameters,
    BRACKET_CONFIG, BRACKET_RANGES, TRADE_SIZES, TAKE_PROFIT_PERCENTAGES
)
from config import config
from typing import List, Optional, Dict, Any, Generator
from contextlib import contextmanager
import os
import logging
from datetime import datetime

# Logger setup
logger = logging.getLogger(__name__)

# Database configuration - use config for absolute path
DATABASE_URL = config.DATABASE_URL
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
    from pathlib import Path
    db = SessionLocal()
    try:
        # Check if profiles already exist
        existing_profiles = db.query(Profile).count()
        if existing_profiles == 0:
            # Generate secure API keys
            api_key_1 = f"bullx_{secrets.token_urlsafe(32)}"
            api_key_2 = f"bullx_{secrets.token_urlsafe(32)}"

            # Create default profiles using platform-aware paths from config
            profile1 = Profile(
                name="Saruman",
                chrome_profile_path=config.CHROME_PROFILES.get("Saruman", ""),
                api_key=api_key_1
            )
            profile2 = Profile(
                name="Gandalf",
                chrome_profile_path=config.CHROME_PROFILES.get("Gandalf", ""),
                api_key=api_key_2
            )

            db.add(profile1)
            db.add(profile2)
            db.commit()

            # Save API keys to file for safekeeping
            keys_file = Path(__file__).parent / "api_keys.txt"
            with open(keys_file, "w") as f:
                f.write("BullX Automation API Keys\n")
                f.write("=" * 40 + "\n")
                f.write(f"Saruman: {api_key_1}\n")
                f.write(f"Gandalf: {api_key_2}\n")
                f.write("=" * 40 + "\n")
                f.write("IMPORTANT: Keep this file secure!\n")

            logger.warning("Default profiles created. API keys saved to api_keys.txt")
            logger.warning(f"  Saruman: {api_key_1}")
            logger.warning(f"  Gandalf: {api_key_2}")
    except Exception as e:
        logger.error(f"Error initializing profiles: {e}")
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
        """Update order status with proper timestamp handling"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = status
                order.updated_at = datetime.now()
                
                # Set completed_at when marking as COMPLETED
                if status == "COMPLETED":
                    order.completed_at = datetime.now()
                
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def update_order_trigger_condition(self, order_id: int, trigger_condition: str) -> bool:
        """Update order trigger condition with timestamp"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.trigger_condition = trigger_condition
                order.updated_at = datetime.now()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def update_order_amount(self, order_id: int, order_amount: str) -> bool:
        """Update order amount field with the value displayed in BullX Orders tab"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.order_amount = order_amount
                order.updated_at = datetime.now()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def update_order_with_bullx_refresh(self, order_id: int, trigger_condition: str, bullx_update_time: datetime) -> bool:
        """Update order with BullX automation refresh - sets trigger condition and calculated BullX update time"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.trigger_condition = trigger_condition
                order.updated_at = bullx_update_time  # Use calculated BullX update time
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
    
    def get_coin_by_name(self, name: str) -> Optional[Coin]:
        """Get coin by name"""
        db = self.SessionLocal()
        try:
            return db.query(Coin).filter(Coin.name == name).first()
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
        """Mark an order as completed or stopped with proper timestamp handling"""
        db = self.SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = status
                order.updated_at = datetime.now()
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
    
    def get_active_order_by_bracket(self, coin_id: int, bracket_id: int, profile_name: str) -> Optional[Order]:
        """
        Get active order by coin_id, bracket_id, and profile_name.
        Used to prevent duplicate orders during renewal.
        
        Args:
            coin_id: Coin database ID
            bracket_id: Bracket ID (1-4)
            profile_name: Profile name
            
        Returns:
            Active order if exists, None otherwise
        """
        db = self.SessionLocal()
        try:
            return db.query(Order).filter(
                Order.coin_id == coin_id,
                Order.bracket_id == bracket_id,
                Order.profile_name == profile_name,
                Order.status == "ACTIVE"
            ).first()
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
    
    def clear_coin_data(self, address: str, profile_name: str, orders_only: bool = False) -> dict:
        """Clear coin data and/or orders from database"""
        db = self.SessionLocal()
        try:
            # Get the coin
            coin = db.query(Coin).filter(Coin.address == address).first()
            if not coin:
                return {"success": False, "error": "Coin not found"}
            
            # Count orders to be cleared for this profile
            orders_to_clear = db.query(Order).filter(
                Order.coin_id == coin.id,
                Order.profile_name == profile_name
            ).all()
            
            orders_cleared = len(orders_to_clear)
            
            # Delete orders for this profile
            for order in orders_to_clear:
                db.delete(order)
            
            coin_removed = False
            if not orders_only:
                # Check if there are any remaining orders for this coin from other profiles
                remaining_orders = db.query(Order).filter(
                    Order.coin_id == coin.id
                ).count()
                
                # If no orders remain, delete the coin
                if remaining_orders == 0:
                    db.delete(coin)
                    coin_removed = True
            
            db.commit()
            
            return {
                "success": True,
                "orders_cleared": orders_cleared,
                "coin_removed": coin_removed
            }
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def clear_all_profile_data(self, profile_name: str) -> dict:
        """Clear all coins and orders for a specific profile"""
        db = self.SessionLocal()
        try:
            # Get all orders for this profile
            orders_to_clear = db.query(Order).filter(
                Order.profile_name == profile_name
            ).all()
            
            orders_cleared = len(orders_to_clear)
            
            # Get unique coin IDs from these orders
            coin_ids_with_orders = set(order.coin_id for order in orders_to_clear)
            
            # Delete all orders for this profile
            for order in orders_to_clear:
                db.delete(order)
            
            # Check which coins can be deleted (no remaining orders from other profiles)
            coins_to_delete = []
            for coin_id in coin_ids_with_orders:
                remaining_orders = db.query(Order).filter(
                    Order.coin_id == coin_id,
                    Order.profile_name != profile_name
                ).count()
                
                if remaining_orders == 0:
                    coin = db.query(Coin).filter(Coin.id == coin_id).first()
                    if coin:
                        coins_to_delete.append(coin)
            
            # Delete coins with no remaining orders
            for coin in coins_to_delete:
                db.delete(coin)
            
            coins_cleared = len(coins_to_delete)
            
            db.commit()
            
            return {
                "success": True,
                "orders_cleared": orders_cleared,
                "coins_cleared": coins_cleared
            }
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    # ---- Queue management methods ----

    def add_to_queue(self, profile_name: str, address: str, total_amount: float,
                     bracket: Optional[int] = None, priority: int = 0) -> QueuedExecution:
        """Add a bracket strategy execution to the queue"""
        db = self.SessionLocal()
        try:
            queued = QueuedExecution(
                profile_name=profile_name,
                address=address,
                total_amount=total_amount,
                bracket=bracket,
                priority=priority,
                status="QUEUED"
            )
            db.add(queued)
            db.commit()
            db.refresh(queued)
            return queued
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def get_queue_items(self, profile_name: Optional[str] = None,
                        status: Optional[str] = None) -> List[QueuedExecution]:
        """Get queue items, optionally filtered by profile and/or status"""
        db = self.SessionLocal()
        try:
            query = db.query(QueuedExecution)
            if profile_name:
                query = query.filter(QueuedExecution.profile_name == profile_name)
            if status:
                query = query.filter(QueuedExecution.status == status)
            return query.order_by(
                QueuedExecution.priority.desc(),
                QueuedExecution.created_at.asc()
            ).all()
        finally:
            db.close()

    def get_queue_item(self, item_id: int) -> Optional[QueuedExecution]:
        """Get a single queue item by ID"""
        db = self.SessionLocal()
        try:
            return db.query(QueuedExecution).filter(QueuedExecution.id == item_id).first()
        finally:
            db.close()

    def get_next_queued_item(self, profile_name: str) -> Optional[QueuedExecution]:
        """Get the next QUEUED item for a profile (by priority DESC, then created_at ASC)"""
        db = self.SessionLocal()
        try:
            return db.query(QueuedExecution).filter(
                QueuedExecution.profile_name == profile_name,
                QueuedExecution.status == "QUEUED"
            ).order_by(
                QueuedExecution.priority.desc(),
                QueuedExecution.created_at.asc()
            ).first()
        finally:
            db.close()

    def is_profile_queue_busy(self, profile_name: str) -> bool:
        """Check if a profile has any IN_PROGRESS items"""
        db = self.SessionLocal()
        try:
            count = db.query(QueuedExecution).filter(
                QueuedExecution.profile_name == profile_name,
                QueuedExecution.status == "IN_PROGRESS"
            ).count()
            return count > 0
        finally:
            db.close()

    def update_queue_item_status(self, item_id: int, status: str,
                                  error_message: Optional[str] = None,
                                  result_json: Optional[str] = None) -> bool:
        """Update queue item status with timestamps"""
        db = self.SessionLocal()
        try:
            item = db.query(QueuedExecution).filter(QueuedExecution.id == item_id).first()
            if not item:
                return False
            item.status = status
            if status == "IN_PROGRESS":
                item.started_at = datetime.now()
            elif status in ("COMPLETED", "FAILED"):
                item.completed_at = datetime.now()
            if error_message is not None:
                item.error_message = error_message
            if result_json is not None:
                item.result_json = result_json
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def cancel_queue_item(self, item_id: int) -> bool:
        """Cancel a QUEUED item (only if still QUEUED)"""
        db = self.SessionLocal()
        try:
            item = db.query(QueuedExecution).filter(
                QueuedExecution.id == item_id,
                QueuedExecution.status == "QUEUED"
            ).first()
            if not item:
                return False
            db.delete(item)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def retry_queue_item(self, item_id: int) -> Optional[QueuedExecution]:
        """Reset a FAILED item back to QUEUED for retry"""
        db = self.SessionLocal()
        try:
            item = db.query(QueuedExecution).filter(
                QueuedExecution.id == item_id,
                QueuedExecution.status == "FAILED"
            ).first()
            if not item:
                return None
            item.status = "QUEUED"
            item.started_at = None
            item.completed_at = None
            item.error_message = None
            item.result_json = None
            db.commit()
            db.refresh(item)
            return item
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def clear_completed_queue_items(self, profile_name: Optional[str] = None) -> int:
        """Clear completed and failed items from the queue"""
        db = self.SessionLocal()
        try:
            query = db.query(QueuedExecution).filter(
                QueuedExecution.status.in_(["COMPLETED", "FAILED"])
            )
            if profile_name:
                query = query.filter(QueuedExecution.profile_name == profile_name)
            count = query.delete(synchronize_session='fetch')
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    # ---- Atomic transaction and duplicate detection methods ----

    @contextmanager
    def atomic_transaction(self) -> Generator[Session, None, None]:
        """
        Context manager for atomic database transactions.
        All operations within the context either commit together or rollback together.

        Usage:
            with db_manager.atomic_transaction() as session:
                # Multiple operations
                session.add(order)
                session.flush()
                # All commit or all rollback
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
            logger.info("✅ Transaction committed successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Transaction rolled back due to error: {e}")
            raise
        finally:
            session.close()

    def mark_order_for_replacement(self, order_id: int, new_status: str = "REPLACED") -> bool:
        """
        Mark an order as REPLACED (or other status) atomically.
        Used during renewal process.

        Args:
            order_id: Order ID to update
            new_status: New status (default: REPLACED)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.atomic_transaction() as session:
                order = session.query(Order).filter(Order.id == order_id).first()
                if not order:
                    logger.error(f"Order {order_id} not found")
                    return False

                old_status = order.status
                order.status = new_status
                order.updated_at = datetime.now()
                if new_status in ["COMPLETED", "STOPPED", "EXPIRED", "REPLACED"]:
                    order.completed_at = datetime.now()
                session.flush()

                logger.info(f"✅ Order {order_id} status: {old_status} → {new_status}")
                return True
        except Exception as e:
            logger.error(f"Failed to mark order {order_id} as {new_status}: {e}")
            return False

    def detect_duplicate_active_orders(self, profile_name: Optional[str] = None) -> List[dict]:
        """
        Detect duplicate ACTIVE orders with same (coin_id, bracket_id, profile_name).

        Args:
            profile_name: Optional profile filter

        Returns:
            List of duplicate groups with order details
        """
        db = self.SessionLocal()
        try:
            from sqlalchemy import func

            # Query for duplicates
            query = db.query(
                Order.coin_id,
                Order.bracket_id,
                Order.profile_name,
                func.count(Order.id).label('count')
            ).filter(
                Order.status == "ACTIVE"
            ).group_by(
                Order.coin_id,
                Order.bracket_id,
                Order.profile_name
            ).having(
                func.count(Order.id) > 1
            )

            if profile_name:
                query = query.filter(Order.profile_name == profile_name)

            duplicates = query.all()

            # Get detailed order info for each duplicate group
            result = []
            for dup in duplicates:
                orders = db.query(Order).filter(
                    Order.coin_id == dup.coin_id,
                    Order.bracket_id == dup.bracket_id,
                    Order.profile_name == dup.profile_name,
                    Order.status == "ACTIVE"
                ).order_by(Order.created_at).all()

                coin = db.query(Coin).filter(Coin.id == dup.coin_id).first()

                result.append({
                    'coin_id': dup.coin_id,
                    'coin_name': coin.name if coin else 'Unknown',
                    'bracket_id': dup.bracket_id,
                    'profile_name': dup.profile_name,
                    'count': dup.count,
                    'orders': [
                        {
                            'id': o.id,
                            'created_at': o.created_at,
                            'amount': o.amount
                        } for o in orders
                    ]
                })

            return result
        finally:
            db.close()

    def fix_duplicate_active_orders(self, dry_run: bool = False) -> int:
        """
        Fix duplicate ACTIVE orders by marking older duplicates as REPLACED.
        Keeps the newest order for each (coin_id, bracket_id, profile_name) group.

        Args:
            dry_run: If True, only log what would be fixed without making changes

        Returns:
            Number of orders marked as REPLACED
        """
        duplicates = self.detect_duplicate_active_orders()

        if not duplicates:
            logger.info("✅ No duplicate ACTIVE orders found")
            return 0

        logger.warning(f"⚠️  Found {len(duplicates)} duplicate groups")

        fixed_count = 0

        for dup_group in duplicates:
            logger.warning(f"   Duplicate: Coin {dup_group['coin_name']}, Bracket {dup_group['bracket_id']}")
            logger.warning(f"   {dup_group['count']} ACTIVE orders found:")

            # Sort by created_at, keep newest
            orders = sorted(dup_group['orders'], key=lambda x: x['created_at'])

            for order in orders[:-1]:  # All except newest
                logger.warning(f"      Order {order['id']}: {order['created_at']} [WILL MARK AS REPLACED]")

                if not dry_run:
                    success = self.mark_order_for_replacement(order['id'], "REPLACED")
                    if success:
                        fixed_count += 1

            # Keep newest
            newest = orders[-1]
            logger.info(f"      Order {newest['id']}: {newest['created_at']} [KEEPING]")

        if dry_run:
            logger.info(f"🔍 DRY RUN: Would fix {len(duplicates)} duplicate groups")
        else:
            logger.info(f"✅ Fixed {fixed_count} duplicate orders")

        return fixed_count

    def detect_stale_active_orders(self, max_age_hours: int = 72, profile_name: Optional[str] = None) -> List[Order]:
        """
        Detect ACTIVE orders older than specified hours.
        These may be stuck and need manual review.

        Args:
            max_age_hours: Maximum age in hours (default: 72 hours = 3 days)
            profile_name: Optional profile filter

        Returns:
            List of stale orders
        """
        from datetime import timedelta

        db = self.SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            query = db.query(Order).filter(
                Order.status == "ACTIVE",
                Order.created_at < cutoff_time
            )

            if profile_name:
                query = query.filter(Order.profile_name == profile_name)

            stale_orders = query.all()

            if stale_orders:
                logger.warning(f"⚠️  Found {len(stale_orders)} stale ACTIVE orders (older than {max_age_hours}h)")
                for order in stale_orders:
                    age_hours = (datetime.now() - order.created_at).total_seconds() / 3600
                    logger.warning(f"   Order {order.id}: {age_hours:.1f}h old, bracket {order.bracket_id}")

            return stale_orders
        finally:
            db.close()

# Global database manager instance
db_manager = DatabaseManager()
