import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import db_manager
from models import Order
from task_persistence import save_task_execution
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TaskExecution:
    """Track task execution details"""
    profile_name: str
    scheduled_time: datetime
    actual_start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    orders_processed: int = 0
    missed: bool = False

class EnhancedOrderMonitor:
    """Enhanced order monitor with missed task detection and recovery"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.monitored_profiles = set()
        self.task_history: Dict[str, List[TaskExecution]] = {}
        self.last_successful_run: Dict[str, datetime] = {}
        self.max_history_size = 100
        self.task_timeout = 300  # 5 minutes timeout per task
        
    async def start_monitoring_for_profile(self, profile_name: str, interval_minutes: int = 5):
        """Start enhanced background order monitoring for a specific profile"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Enhanced order monitoring scheduler started")
        
        # Initialize task history for profile
        if profile_name not in self.task_history:
            self.task_history[profile_name] = []
        
        # Add profile-specific job if not already monitoring this profile
        job_id = f'order_checker_{profile_name}'
        if profile_name not in self.monitored_profiles:
            self.scheduler.add_job(
                self._execute_monitored_task,
                trigger=IntervalTrigger(minutes=interval_minutes),
                args=[profile_name],
                id=job_id,
                name=f'Enhanced Check Orders Status for {profile_name}',
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                misfire_grace_time=60  # Allow 1 minute grace for missed tasks
            )
            self.monitored_profiles.add(profile_name)
            logger.info(f"Enhanced order monitoring started for profile {profile_name} - checking every {interval_minutes} minutes")
    
    async def stop_monitoring_for_profile(self, profile_name: str):
        """Stop background order monitoring for a specific profile"""
        job_id = f'order_checker_{profile_name}'
        try:
            self.scheduler.remove_job(job_id)
            self.monitored_profiles.discard(profile_name)
            logger.info(f"Enhanced order monitoring stopped for profile {profile_name}")
        except Exception as e:
            logger.error(f"Error stopping monitoring for profile {profile_name}: {e}")
    
    async def stop_monitoring(self):
        """Stop all background order monitoring"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            self.monitored_profiles.clear()
            logger.info("Enhanced order monitoring stopped")
    
    async def _execute_monitored_task(self, profile_name: str):
        """Execute a monitored task with tracking and error handling"""
        scheduled_time = datetime.now()
        task_execution = TaskExecution(
            profile_name=profile_name,
            scheduled_time=scheduled_time,
            actual_start_time=datetime.now()
        )
        
        try:
            # Check for missed tasks before executing current one
            await self._check_for_missed_tasks(profile_name)
            
            # Execute the actual order checking task
            logger.info(f"Starting enhanced order check for profile: {profile_name}")
            
            # Import the API function to reuse the logic
            from routers.secure import check_orders_service
            
            result = await asyncio.wait_for(
                check_orders_service(profile_name),
                timeout=self.task_timeout
            )
            
            if result["success"]:
                task_execution.success = True
                task_execution.orders_processed = result.get('total_buttons', 0)
                logger.info(f"Successfully processed {task_execution.orders_processed} buttons for {profile_name}")
                
                # Process the extracted order information
                await self.process_order_information(profile_name, result["order_info"])
                
                # Update last successful run time
                self.last_successful_run[profile_name] = datetime.now()
                
            else:
                task_execution.success = False
                task_execution.error_message = result.get('error', 'Unknown error')
                logger.error(f"Order check failed for {profile_name}: {task_execution.error_message}")
            
            # Also check individual active orders from database for this profile
            active_orders = db_manager.get_active_orders_by_profile(profile_name)
            logger.info(f"Also checking {len(active_orders)} active orders from database for {profile_name}")
            
            for order in active_orders:
                await self.check_single_order(order)
            
        except asyncio.TimeoutError:
            task_execution.success = False
            task_execution.error_message = f"Task timed out after {self.task_timeout} seconds"
            logger.error(f"Task timeout for profile {profile_name}")
            
        except Exception as e:
            task_execution.success = False
            task_execution.error_message = str(e)
            logger.error(f"Error in enhanced order check for profile {profile_name}: {e}")
        
        finally:
            task_execution.completion_time = datetime.now()
            
            # Close the driver when done
            try:
                from chrome_driver import chrome_driver_manager
                chrome_driver_manager.close_driver(profile_name)
                logger.info(f"Closed Chrome driver for profile: {profile_name}")
            except Exception as e:
                logger.error(f"Error closing driver for profile {profile_name}: {e}")
            
            # Record task execution
            self._record_task_execution(task_execution)
    
    async def _check_for_missed_tasks(self, profile_name: str):
        """Check if any tasks were missed and attempt recovery"""
        if profile_name not in self.last_successful_run:
            # First run for this profile
            return
        
        last_run = self.last_successful_run[profile_name]
        current_time = datetime.now()
        time_since_last_run = current_time - last_run
        
        # If more than 10 minutes have passed since last successful run, consider tasks missed
        expected_interval = timedelta(minutes=5)
        grace_period = timedelta(minutes=2)
        
        if time_since_last_run > (expected_interval + grace_period):
            missed_intervals = int(time_since_last_run.total_seconds() / expected_interval.total_seconds()) - 1
            
            if missed_intervals > 0:
                logger.warning(f"Detected {missed_intervals} missed task intervals for profile {profile_name}")
                
                # Record missed tasks
                for i in range(missed_intervals):
                    missed_time = last_run + (expected_interval * (i + 1))
                    missed_task = TaskExecution(
                        profile_name=profile_name,
                        scheduled_time=missed_time,
                        missed=True,
                        error_message="Task execution was missed"
                    )
                    self._record_task_execution(missed_task)
                
                # Attempt catch-up logic
                await self._perform_catch_up_check(profile_name, time_since_last_run)
    
    async def _perform_catch_up_check(self, profile_name: str, time_gap: timedelta):
        """Perform catch-up checks for missed monitoring periods"""
        logger.info(f"Performing catch-up check for profile {profile_name} (gap: {time_gap})")
        
        try:
            # Get all active orders for this profile
            active_orders = db_manager.get_active_orders_by_profile(profile_name)
            
            # For each active order, perform a more thorough check
            # since we might have missed status changes
            catch_up_results = []
            
            for order in active_orders:
                try:
                    # Check if order might have completed during the gap
                    order_age = datetime.now() - order.created_at
                    
                    # If order is older than the gap, it might have completed
                    if order_age > time_gap:
                        result = await self.check_single_order(order, force_check=True)
                        catch_up_results.append(result)
                        
                except Exception as e:
                    logger.error(f"Error in catch-up check for order {order.id}: {e}")
            
            logger.info(f"Catch-up check completed for {profile_name}. Checked {len(catch_up_results)} orders")
            
        except Exception as e:
            logger.error(f"Error performing catch-up check for {profile_name}: {e}")
    
    def _record_task_execution(self, task_execution: TaskExecution):
        """Record task execution in history and database"""
        profile_name = task_execution.profile_name
        
        # Keep in-memory history for quick access
        if profile_name not in self.task_history:
            self.task_history[profile_name] = []
        
        self.task_history[profile_name].append(task_execution)
        
        # Maintain history size limit
        if len(self.task_history[profile_name]) > self.max_history_size:
            self.task_history[profile_name] = self.task_history[profile_name][-self.max_history_size:]
        
        # Save to database for persistence
        try:
            task_data = {
                'profile_name': task_execution.profile_name,
                'scheduled_time': task_execution.scheduled_time,
                'actual_start_time': task_execution.actual_start_time,
                'completion_time': task_execution.completion_time,
                'success': task_execution.success,
                'missed': task_execution.missed,
                'error_message': task_execution.error_message,
                'orders_processed': task_execution.orders_processed,
                'task_type': 'order_check'
            }
            
            task_id = save_task_execution(task_data)
            if task_id:
                logger.debug(f"Saved task execution {task_id} to database for {profile_name}")
            else:
                logger.warning(f"Failed to save task execution to database for {profile_name}")
                
        except Exception as e:
            logger.error(f"Error saving task execution to database: {e}")
        
        # Log execution details
        if task_execution.missed:
            logger.warning(f"Recorded missed task for {profile_name} at {task_execution.scheduled_time}")
        elif task_execution.success:
            duration = (task_execution.completion_time - task_execution.actual_start_time).total_seconds()
            logger.info(f"Task completed successfully for {profile_name} in {duration:.2f}s")
        else:
            logger.error(f"Task failed for {profile_name}: {task_execution.error_message}")
    
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
                        logger.info(f"  Row data: {main_text[:100]}...")
                        
                        if href:
                            logger.info(f"    Link: {href}")
                        
                    except Exception as e:
                        logger.error(f"Error processing row in button {button_index}: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing order information for {profile_name}: {e}")
    
    async def check_single_order(self, order: Order, force_check: bool = False):
        """Check a single order status and re-enter if completed"""
        try:
            # Get order status from BullX interface
            order_status = await self.get_order_status_from_bullx(order)
            
            if order_status in ["COMPLETED", "STOPPED"]:
                logger.info(f"Order {order.id} has {order_status}, re-entering...")
                
                # Update order status in database
                db_manager.update_order_status(order.id, order_status)
                
                # Calculate new parameters based on current market cap
                new_params = await self.calculate_new_order_parameters(order)
                
                if new_params:
                    # Place new order using the bracket order placement system
                    from bracket_order_placement import place_bracket_order
                    
                    success = await place_bracket_order(
                        profile_name=order.profile_name,
                        strategy_number=order.strategy_number,
                        address=order.coin.address,
                        order_type=order.order_type,
                        entry_price=new_params['entry_price'],
                        take_profit=new_params['take_profit'],
                        stop_loss=new_params['stop_loss']
                    )
                    
                    if success:
                        logger.info(f"Successfully re-entered order for {order.coin.address}")
                        return {"success": True, "action": "re-entered"}
                    else:
                        logger.error(f"Failed to re-enter order for {order.coin.address}")
                        return {"success": False, "action": "re-entry_failed"}
                else:
                    logger.error(f"Could not calculate new parameters for order {order.id}")
                    return {"success": False, "action": "parameter_calculation_failed"}
            
            return {"success": True, "action": "no_action_needed", "status": order_status}
            
        except Exception as e:
            logger.error(f"Error checking order {order.id}: {e}")
            return {"success": False, "action": "check_failed", "error": str(e)}
    
    async def get_order_status_from_bullx(self, order: Order) -> str:
        """Get order status from BullX interface"""
        try:
            # This is a placeholder implementation
            # You'll need to implement actual order status checking based on BullX UI
            
            # For now, we'll return ACTIVE (you can implement actual checking later)
            return "ACTIVE"
            
        except Exception as e:
            logger.error(f"Error getting order status for order {order.id}: {e}")
            return "UNKNOWN"
    
    async def calculate_new_order_parameters(self, order: Order) -> dict:
        """Calculate new order parameters based on current market conditions"""
        try:
            # Get current market cap using the chrome driver
            from chrome_driver import chrome_driver_manager
            
            driver = chrome_driver_manager.get_driver(order.profile_name)
            if not driver:
                logger.error(f"Could not get driver for profile {order.profile_name}")
                return None
            
            # Navigate to the coin page to get current market cap
            coin_url = f"https://neo.bullx.io/terminal/{order.coin.address}"
            driver.get(coin_url)
            
            # Wait for page to load and extract market cap
            # This is a placeholder - you'll need to implement actual market cap extraction
            current_market_cap = order.market_cap  # Fallback to original market cap
            
            if current_market_cap == 0:
                logger.error(f"Could not get market cap for {order.coin.address}")
                return None
            
            # Calculate new parameters based on market cap change
            market_cap_ratio = current_market_cap / order.market_cap if order.market_cap > 0 else 1
            
            # Adjust parameters based on strategy
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
            
            return params
            
        except Exception as e:
            logger.error(f"Error applying strategy {strategy_number} adjustments: {e}")
            return params
    
    def get_task_health_status(self, profile_name: str = None) -> dict:
        """Get health status of background tasks"""
        if profile_name:
            profiles = [profile_name] if profile_name in self.monitored_profiles else []
        else:
            profiles = list(self.monitored_profiles)
        
        health_status = {
            "scheduler_running": self.is_running,
            "monitored_profiles": list(self.monitored_profiles),
            "profiles": {}
        }
        
        for profile in profiles:
            profile_history = self.task_history.get(profile, [])
            recent_tasks = [t for t in profile_history if t.scheduled_time > datetime.now() - timedelta(hours=1)]
            
            successful_tasks = [t for t in recent_tasks if t.success and not t.missed]
            failed_tasks = [t for t in recent_tasks if not t.success and not t.missed]
            missed_tasks = [t for t in recent_tasks if t.missed]
            
            last_successful = self.last_successful_run.get(profile)
            time_since_last_success = None
            if last_successful:
                time_since_last_success = (datetime.now() - last_successful).total_seconds()
            
            health_status["profiles"][profile] = {
                "last_successful_run": last_successful.isoformat() if last_successful else None,
                "time_since_last_success_seconds": time_since_last_success,
                "recent_successful_tasks": len(successful_tasks),
                "recent_failed_tasks": len(failed_tasks),
                "recent_missed_tasks": len(missed_tasks),
                "total_task_history": len(profile_history),
                "is_healthy": len(missed_tasks) == 0 and len(failed_tasks) < len(successful_tasks)
            }
        
        return health_status
    
    def get_task_execution_history(self, profile_name: str, limit: int = 20) -> List[dict]:
        """Get task execution history for a profile"""
        if profile_name not in self.task_history:
            return []
        
        history = self.task_history[profile_name][-limit:]
        
        return [
            {
                "scheduled_time": task.scheduled_time.isoformat(),
                "actual_start_time": task.actual_start_time.isoformat() if task.actual_start_time else None,
                "completion_time": task.completion_time.isoformat() if task.completion_time else None,
                "success": task.success,
                "missed": task.missed,
                "error_message": task.error_message,
                "orders_processed": task.orders_processed,
                "duration_seconds": (task.completion_time - task.actual_start_time).total_seconds() if task.completion_time and task.actual_start_time else None
            }
            for task in history
        ]

# Global enhanced order monitor instance
enhanced_order_monitor = EnhancedOrderMonitor()

# Compatibility functions for existing code
async def start_background_tasks():
    """Start all background tasks (deprecated - use profile-specific functions)"""
    logger.warning("start_background_tasks() is deprecated. Use start_background_tasks_for_profile(profile_name) instead.")
    profiles = ["Saruman", "Gandalf"]
    for profile_name in profiles:
        await enhanced_order_monitor.start_monitoring_for_profile(profile_name)

async def stop_background_tasks():
    """Stop all background tasks"""
    await enhanced_order_monitor.stop_monitoring()

async def start_background_tasks_for_profile(profile_name: str):
    """Start enhanced background tasks for a specific profile"""
    await enhanced_order_monitor.start_monitoring_for_profile(profile_name)

async def stop_background_tasks_for_profile(profile_name: str):
    """Stop enhanced background tasks for a specific profile"""
    await enhanced_order_monitor.stop_monitoring_for_profile(profile_name)

async def check_orders_for_profile(profile_name: str):
    """Manually trigger order check for a specific profile"""
    await enhanced_order_monitor._execute_monitored_task(profile_name)

def get_background_task_health(profile_name: str = None) -> dict:
    """Get health status of background tasks"""
    return enhanced_order_monitor.get_task_health_status(profile_name)

def get_task_execution_history(profile_name: str, limit: int = 20) -> List[dict]:
    """Get task execution history for a profile"""
    return enhanced_order_monitor.get_task_execution_history(profile_name, limit)
