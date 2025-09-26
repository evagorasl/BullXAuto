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
        self.monitored_profiles = set()
    
    async def start_monitoring_for_profile(self, profile_name: str):
        """Start background order monitoring for a specific profile"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Order monitoring scheduler started")
        
        # Add profile-specific job if not already monitoring this profile
        job_id = f'order_checker_{profile_name}'
        if profile_name not in self.monitored_profiles:
            self.scheduler.add_job(
                self.check_orders,
                trigger=IntervalTrigger(minutes=5),
                args=[profile_name],
                id=job_id,
                name=f'Check Orders Status for {profile_name}',
                replace_existing=True
            )
            self.monitored_profiles.add(profile_name)
            logger.info(f"Order monitoring started for profile {profile_name} - checking every 5 minutes")
    
    async def stop_monitoring_for_profile(self, profile_name: str):
        """Stop background order monitoring for a specific profile"""
        job_id = f'order_checker_{profile_name}'
        try:
            self.scheduler.remove_job(job_id)
            self.monitored_profiles.discard(profile_name)
            logger.info(f"Order monitoring stopped for profile {profile_name}")
        except Exception as e:
            logger.error(f"Error stopping monitoring for profile {profile_name}: {e}")
    
    async def start_monitoring(self):
        """Start the background order monitoring (deprecated - use start_monitoring_for_profile)"""
        logger.warning("start_monitoring() is deprecated. Use start_monitoring_for_profile(profile_name) instead.")
        # For backward compatibility, we'll start monitoring for all profiles
        profiles = self._get_all_profiles()
        for profile_name in profiles:
            await self.start_monitoring_for_profile(profile_name)
    
    async def stop_monitoring(self):
        """Stop the background order monitoring"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Order monitoring stopped")
    
    async def check_orders(self, profile_name: str):
        """Check active orders for a specific profile by navigating to automation page and extracting information"""
        try:
            logger.info(f"Starting order check for profile: {profile_name}")
            
            # Import the API function to reuse the logic
            from routers.secure import check_orders_service
            
            try:
                logger.info(f"Checking orders for profile: {profile_name}")
                
                # Use the shared service function from the API
                result = await check_orders_service(profile_name)
                
                if result["success"]:
                    logger.info(f"Successfully processed {result['total_buttons']} buttons for {profile_name}")
                    
                    # Process the extracted order information
                    await self.process_order_information(profile_name, result["order_info"])
                    
                else:
                    logger.error(f"Order check failed for {profile_name}: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error checking orders for profile {profile_name}: {e}")
            
            # Also check individual active orders from database for this profile
            active_orders = db_manager.get_active_orders_by_profile(profile_name)
            logger.info(f"Also checking {len(active_orders)} active orders from database for {profile_name}")
            
            for order in active_orders:
                await self.check_single_order(order)
            
            # Close the driver when done
            try:
                from chrome_driver import chrome_driver_manager
                chrome_driver_manager.close_driver(profile_name)
                logger.info(f"Closed Chrome driver for profile: {profile_name}")
            except Exception as e:
                logger.error(f"Error closing driver for profile {profile_name}: {e}")
                
        except Exception as e:
            logger.error(f"Error in check_orders for profile {profile_name}: {e}")
    
    def _get_all_profiles(self) -> List[str]:
        """Get all profile names from database"""
        try:
            # Get all profiles from database
            profiles = []
            saruman_profile = db_manager.get_profile_by_name("Saruman")
            gandalf_profile = db_manager.get_profile_by_name("Gandalf")
            
            if saruman_profile:
                profiles.append("Saruman")
            if gandalf_profile:
                profiles.append("Gandalf")
            
            return profiles
        except Exception as e:
            logger.error(f"Error getting profiles: {e}")
            return ["Saruman", "Gandalf"]  # Fallback to default profiles
    
    async def process_order_information(self, profile_name: str, order_info: list):
        """Process the extracted order information from automation page"""
        try:
            logger.info(f"Processing order information for {profile_name}")
            
            for button_info in order_info:
                button_index = button_info.get("button_index", "Unknown")
                rows = button_info.get("rows", [])
                
                logger.info(f"Processing button {button_index} with {len(rows)} rows")
                
                for row in rows:
                    try:
                        # Extract relevant information from each row
                        main_text = row.get("main_text", "")
                        href = row.get("href", "")
                        
                        # Log the extracted information for now
                        # You can extend this to parse specific order details and update database
                        logger.info(f"  Row data: {main_text[:100]}...")
                        
                        # Example: Parse order status, coin name, amounts, etc.
                        # This is where you would implement specific parsing logic
                        # based on the actual structure of the BullX automation page
                        
                        # For now, just output the information
                        if href:
                            logger.info(f"    Link: {href}")
                        
                    except Exception as e:
                        logger.error(f"Error processing row in button {button_index}: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing order information for {profile_name}: {e}")
    
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

async def start_background_tasks_for_profile(profile_name: str):
    """Start background tasks for a specific profile"""
    await order_monitor.start_monitoring_for_profile(profile_name)

async def stop_background_tasks_for_profile(profile_name: str):
    """Stop background tasks for a specific profile"""
    await order_monitor.stop_monitoring_for_profile(profile_name)

async def check_orders_for_profile(profile_name: str):
    """Manually trigger order check for a specific profile"""
    await order_monitor.check_orders(profile_name)
