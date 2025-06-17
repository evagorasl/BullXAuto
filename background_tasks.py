import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import db_manager
from chrome_driver import bullx_automator
from typing import List
from models import Order

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrderMonitor:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    async def start_monitoring(self):
        """Start the background order monitoring"""
        if not self.is_running:
            # Schedule order checking every 5 minutes
            self.scheduler.add_job(
                self.check_orders,
                trigger=IntervalTrigger(minutes=5),
                id='order_checker',
                name='Check Orders Status',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Order monitoring started - checking every 5 minutes")
    
    async def stop_monitoring(self):
        """Stop the background order monitoring"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Order monitoring stopped")
    
    async def check_orders(self):
        """Check all active orders and re-enter if needed"""
        try:
            active_orders = db_manager.get_active_orders()
            logger.info(f"Checking {len(active_orders)} active orders")
            
            for order in active_orders:
                await self.check_single_order(order)
                
        except Exception as e:
            logger.error(f"Error checking orders: {e}")
    
    async def check_single_order(self, order: Order):
        """Check a single order status and re-enter if completed"""
        try:
            # This is a placeholder for actual order status checking
            # You'll need to implement the actual logic based on BullX UI
            
            # For now, we'll simulate checking order status
            order_status = await self.get_order_status_from_bullx(order)
            
            if order_status in ["COMPLETED", "STOPPED"]:
                logger.info(f"Order {order.id} has {order_status}, re-entering...")
                
                # Update order status in database
                db_manager.update_order_status(order.id, order_status)
                
                # Calculate new parameters based on current market cap
                new_params = await self.calculate_new_order_parameters(order)
                
                if new_params:
                    # Place new order
                    success = bullx_automator.execute_strategy(
                        profile_name=order.profile_name,
                        strategy_number=order.strategy_number,
                        address=order.address,
                        order_type=order.order_type,
                        entry_price=new_params['entry_price'],
                        take_profit=new_params['take_profit'],
                        stop_loss=new_params['stop_loss']
                    )
                    
                    if success:
                        logger.info(f"Successfully re-entered order for {order.address}")
                    else:
                        logger.error(f"Failed to re-enter order for {order.address}")
                        
        except Exception as e:
            logger.error(f"Error checking order {order.id}: {e}")
    
    async def get_order_status_from_bullx(self, order: Order) -> str:
        """Get order status from BullX interface"""
        try:
            # This is a placeholder implementation
            # You'll need to implement actual order status checking based on BullX UI
            
            # For now, we'll return ACTIVE (you can implement actual checking later)
            return "ACTIVE"
            
            # Example implementation (to be customized based on actual BullX UI):
            # driver = bullx_automator.driver_manager.get_driver(order.profile_name)
            # 
            # # Navigate to orders page
            # driver.get("https://neo.bullx.io/orders")  # Adjust URL as needed
            # 
            # # Find the specific order by ID or other identifier
            # order_element = driver.find_element(By.CSS_SELECTOR, f"[data-order-id='{order.order_id_bullx}']")
            # 
            # # Get status from the element
            # status_element = order_element.find_element(By.CSS_SELECTOR, ".order-status")
            # status = status_element.text.upper()
            # 
            # return status
            
        except Exception as e:
            logger.error(f"Error getting order status for order {order.id}: {e}")
            return "UNKNOWN"
    
    async def calculate_new_order_parameters(self, order: Order) -> dict:
        """Calculate new order parameters based on current market conditions"""
        try:
            # Get current market cap
            current_market_cap = bullx_automator.get_market_cap(order.profile_name)
            
            if current_market_cap == 0:
                logger.error(f"Could not get market cap for {order.address}")
                return None
            
            # Calculate new parameters based on market cap change
            market_cap_ratio = current_market_cap / order.market_cap
            
            # Adjust parameters based on strategy (this is a basic example)
            new_entry_price = order.entry_price * market_cap_ratio
            new_take_profit = order.take_profit * market_cap_ratio
            new_stop_loss = order.stop_loss * market_cap_ratio
            
            # Apply strategy-specific adjustments
            new_params = self.apply_strategy_adjustments(
                order.strategy_number,
                {
                    'entry_price': new_entry_price,
                    'take_profit': new_take_profit,
                    'stop_loss': new_stop_loss,
                    'market_cap': current_market_cap
                }
            )
            
            return new_params
            
        except Exception as e:
            logger.error(f"Error calculating new parameters for order {order.id}: {e}")
            return None
    
    def apply_strategy_adjustments(self, strategy_number: int, params: dict) -> dict:
        """Apply strategy-specific adjustments to order parameters"""
        try:
            # Strategy 1: Conservative approach
            if strategy_number == 1:
                params['take_profit'] *= 1.1  # 10% higher take profit
                params['stop_loss'] *= 0.95   # 5% tighter stop loss
            
            # Strategy 2: Aggressive approach
            elif strategy_number == 2:
                params['take_profit'] *= 1.2  # 20% higher take profit
                params['stop_loss'] *= 0.9    # 10% tighter stop loss
            
            # Strategy 3: Market cap based
            elif strategy_number == 3:
                if params['market_cap'] > 1000000:  # > 1M market cap
                    params['take_profit'] *= 1.05  # 5% higher take profit
                    params['stop_loss'] *= 0.98    # 2% tighter stop loss
                else:
                    params['take_profit'] *= 1.15  # 15% higher take profit
                    params['stop_loss'] *= 0.92    # 8% tighter stop loss
            
            # Add more strategies as needed
            
            return params
            
        except Exception as e:
            logger.error(f"Error applying strategy {strategy_number} adjustments: {e}")
            return params

# Global order monitor instance
order_monitor = OrderMonitor()

async def start_background_tasks():
    """Start all background tasks"""
    await order_monitor.start_monitoring()

async def stop_background_tasks():
    """Stop all background tasks"""
    await order_monitor.stop_monitoring()
