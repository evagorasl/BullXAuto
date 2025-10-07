from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging

# Import our modules
from models import (
    LoginRequest, SearchRequest, StrategyRequest, 
    OrderResponse, ProfileResponse, Profile, 
    CoinResponse, OrderDetailResponse, MultiOrderRequest,
    MultiOrderResponse, SubOrderRequest, BracketInfo
)
from database import db_manager
from chrome_driver import bullx_automator, chrome_driver_manager
from auth import get_current_profile
from bracket_config import get_bracket_info as get_bracket_config_info, calculate_order_parameters, BRACKET_CONFIG
from bracket_order_placement import bracket_order_manager
from background_task_monitor import (
    get_background_task_health, get_task_execution_history,
    start_background_tasks_for_profile, stop_background_tasks_for_profile,
    enhanced_order_monitor
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1",
    tags=["secure"],
    responses={404: {"description": "Not found"}},
)

@router.post("/login")
async def login(current_profile: Profile = Depends(get_current_profile)):
    """Login endpoint - opens browser and navigates to BullX for login"""
    try:
        logger.info(f"Login request for profile: {current_profile.name}")
        
        # Attempt login
        success = bullx_automator.login(current_profile.name)
        
        if success:
            #chrome_driver_manager.close_driver(current_profile.name)
            return {
                "success": True,
                "message": f"Logged in for {current_profile.name}.",
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=500, detail="Login failed")
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_address(request: SearchRequest, current_profile: Profile = Depends(get_current_profile)):
    """Search for a specific address/token"""
    try:
        logger.info(f"Search request for address: {request.address} using profile: {current_profile.name}")
        
        # Perform search
        success = bullx_automator.search_address(current_profile.name, request.address)
        
        if success:
            # Get the coin data
            coin = db_manager.get_coin_by_address(request.address)
            
            # If coin exists and has market cap, update its bracket
            if coin and coin.market_cap:
                from bracket_config import calculate_bracket
                new_bracket = calculate_bracket(coin.market_cap)
                
                # Update coin with new bracket if it changed
                if coin.bracket != new_bracket:
                    db_manager.create_or_update_coin(
                        address=request.address,
                        data={"bracket": new_bracket}
                    )
                    coin = db_manager.get_coin_by_address(request.address)  # Refresh coin data
            
            return {
                "success": True,
                "message": f"Successfully searched for address: {request.address}",
                "coin_data": coin,
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=500, detail="Search failed")
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategy")
async def execute_strategy(request: StrategyRequest, current_profile: Profile = Depends(get_current_profile)):
    """Execute a trading strategy"""
    try:
        logger.info(f"Strategy execution request: Strategy {request.strategy_number} for {request.address}")
        
        # Validate order type
        if request.order_type.upper() not in ["BUY", "SELL"]:
            raise HTTPException(status_code=400, detail="Order type must be 'BUY' or 'SELL'")
        
        # If no prices provided, use default strategy-based calculations
        if not all([request.entry_price, request.take_profit, request.stop_loss]):
            # Get current market cap for calculations
            market_cap = bullx_automator.get_market_cap(current_profile.name)
            if market_cap == 0:
                # Search first to get market cap
                search_success = bullx_automator.search_address(current_profile.name, request.address)
                if search_success:
                    market_cap = bullx_automator.get_market_cap(current_profile.name)
            
            if market_cap == 0:
                raise HTTPException(status_code=400, detail="Could not determine market cap. Please provide entry_price, take_profit, and stop_loss manually.")
            
            # Calculate default prices based on strategy and market cap
            prices = calculate_strategy_prices(request.strategy_number, market_cap, request.order_type)
            entry_price = request.entry_price or prices['entry_price']
            take_profit = request.take_profit or prices['take_profit']
            stop_loss = request.stop_loss or prices['stop_loss']
        else:
            entry_price = request.entry_price
            take_profit = request.take_profit
            stop_loss = request.stop_loss
        
        # Execute strategy
        success = bullx_automator.execute_strategy(
            profile_name=current_profile.name,
            strategy_number=request.strategy_number,
            address=request.address,
            order_type=request.order_type.upper(),
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        
        if success:
            return {
                "success": True,
                "message": f"Strategy {request.strategy_number} executed successfully",
                "strategy_number": request.strategy_number,
                "address": request.address,
                "order_type": request.order_type.upper(),
                "entry_price": entry_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=500, detail="Strategy execution failed")
            
    except Exception as e:
        logger.error(f"Strategy execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders", response_model=List[OrderResponse])
async def get_orders(current_profile: Profile = Depends(get_current_profile)):
    """Get active orders for the authenticated profile"""
    try:
        orders = db_manager.get_active_orders_by_profile(current_profile.name)
        return [OrderResponse.from_orm(order) for order in orders]
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(current_profile: Profile = Depends(get_current_profile)):
    """Get current profile information"""
    try:
        return ProfileResponse.from_orm(current_profile)
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coins", response_model=List[CoinResponse])
async def get_coins(current_profile: Profile = Depends(get_current_profile)):
    """Get all coins in the database"""
    try:
        coins = db_manager.get_all_coins()
        return [CoinResponse.from_orm(coin) for coin in coins]
    except Exception as e:
        logger.error(f"Error getting coins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coins/{address}", response_model=CoinResponse)
async def get_coin(address: str, current_profile: Profile = Depends(get_current_profile)):
    """Get coin by address"""
    try:
        coin = db_manager.get_coin_by_address(address)
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin with address {address} not found")
        return CoinResponse.from_orm(coin)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting coin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coins/{address}/orders", response_model=List[OrderResponse])
async def get_coin_orders(
    address: str, 
    status: Optional[str] = Query(None, description="Filter by order status (ACTIVE, COMPLETED, STOPPED)"),
    current_profile: Profile = Depends(get_current_profile)
):
    """Get all orders for a specific coin"""
    try:
        # First get the coin
        coin = db_manager.get_coin_by_address(address)
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin with address {address} not found")
        
        # Get orders for this coin
        orders = db_manager.get_orders_by_coin(coin.id)
        
        # Filter by status if provided
        if status:
            orders = [order for order in orders if order.status == status.upper()]
        
        # Filter by profile
        orders = [order for order in orders if order.profile_name == current_profile.name]
        
        return [OrderResponse.from_orm(order) for order in orders]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting coin orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/close-driver")
async def close_driver(current_profile: Profile = Depends(get_current_profile)):
    """Close Chrome driver for the authenticated profile"""
    try:
        chrome_driver_manager.close_driver(current_profile.name)
        return {
            "success": True,
            "message": f"Chrome driver closed for profile: {current_profile.name}"
        }
    except Exception as e:
        logger.error(f"Error closing driver: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# New multi-order endpoints
@router.post("/multi-order", response_model=MultiOrderResponse)
async def create_multi_order(request: MultiOrderRequest, current_profile: Profile = Depends(get_current_profile)):
    """Create multiple orders for a coin (up to 4 orders with different bracket_ids)"""
    try:
        logger.info(f"Multi-order request for address: {request.address} using profile: {current_profile.name}")
        
        # Validate order type
        if request.order_type.upper() not in ["BUY", "SELL"]:
            raise HTTPException(status_code=400, detail="Order type must be 'BUY' or 'SELL'")
        
        # Validate bracket_ids are unique and within range
        bracket_ids = [order.bracket_id for order in request.orders]
        if len(set(bracket_ids)) != len(bracket_ids):
            raise HTTPException(status_code=400, detail="Bracket IDs must be unique")
        
        if not all(1 <= bid <= 4 for bid in bracket_ids):
            raise HTTPException(status_code=400, detail="Bracket IDs must be between 1 and 4")
        
        if len(request.orders) > 4:
            raise HTTPException(status_code=400, detail="Maximum 4 orders allowed per coin")
        
        # Convert to dict format for database
        sub_orders = []
        for order in request.orders:
            sub_orders.append({
                'bracket_id': order.bracket_id,
                'entry_price': order.entry_price,
                'take_profit': order.take_profit,
                'stop_loss': order.stop_loss,
                'amount': order.amount
            })
        
        # Create multi-order
        result = db_manager.create_multi_order(
            address=request.address,
            strategy_number=request.strategy_number,
            order_type=request.order_type.upper(),
            profile_name=current_profile.name,
            sub_orders=sub_orders
        )
        
        if result["success"]:
            return MultiOrderResponse(
                success=True,
                message=f"Successfully created {result['total_orders_created']} orders for {request.address}",
                coin=CoinResponse.from_orm(result["coin"]),
                orders=[OrderResponse.from_orm(order) for order in result["orders"]],
                total_orders_created=result["total_orders_created"]
            )
        else:
            raise HTTPException(status_code=500, detail="Multi-order creation failed")
            
    except ValueError as e:
        logger.error(f"Multi-order validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Multi-order creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/replace-order/{coin_address}/{bracket_id}")
async def replace_order(
    coin_address: str,
    bracket_id: int,
    new_order: SubOrderRequest,
    current_profile: Profile = Depends(get_current_profile)
):
    """Replace a completed/stopped order with a new one maintaining the same bracket_id"""
    try:
        logger.info(f"Replace order request for {coin_address}, bracket_id: {bracket_id}")
        
        # Validate bracket_id
        if not 1 <= bracket_id <= 4:
            raise HTTPException(status_code=400, detail="Bracket ID must be between 1 and 4")
        
        # Get coin
        coin = db_manager.get_coin_by_address(coin_address)
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin with address {coin_address} not found")
        
        # Prepare new order data
        new_order_data = {
            "strategy_number": 1,  # Default strategy, you might want to make this configurable
            "order_type": "BUY",   # Default type, you might want to make this configurable
            "market_cap": coin.market_cap or 0,
            "entry_price": new_order.entry_price,
            "take_profit": new_order.take_profit,
            "stop_loss": new_order.stop_loss,
            "amount": new_order.amount
        }
        
        # Replace the order
        replaced_order = db_manager.replace_order(
            coin_id=coin.id,
            bracket_id=bracket_id,
            profile_name=current_profile.name,
            new_order_data=new_order_data
        )
        
        return {
            "success": True,
            "message": f"Order replaced successfully for bracket_id {bracket_id}",
            "order": OrderResponse.from_orm(replaced_order)
        }
        
    except Exception as e:
        logger.error(f"Replace order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders-summary")
async def get_orders_summary(current_profile: Profile = Depends(get_current_profile)):
    """Get a summary of active orders grouped by coin and bracket_id"""
    try:
        summary = db_manager.get_active_orders_summary(current_profile.name)
        
        # Convert to a more API-friendly format
        formatted_summary = {}
        for address, data in summary.items():
            formatted_summary[address] = {
                "coin": CoinResponse.from_orm(data["coin"]),
                "bracket": data["bracket"],
                "orders": {
                    str(bracket_id): OrderResponse.from_orm(order) 
                    for bracket_id, order in data["orders"].items()
                }
            }
        
        return {
            "success": True,
            "summary": formatted_summary,
            "total_coins": len(formatted_summary)
        }
        
    except Exception as e:
        logger.error(f"Error getting orders summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/brackets", response_model=List[BracketInfo])
async def get_brackets_info(current_profile: Profile = Depends(get_current_profile)):
    """Get information about market cap brackets"""
    try:
        brackets = []
        for bracket in range(1, 6):  # Brackets 1-5
            info = db_manager.get_bracket_info(bracket)
            brackets.append(BracketInfo(
                bracket=bracket,
                min_market_cap=info["min"],
                max_market_cap=info["max"],
                description=info["description"]
            ))
        
        return brackets
        
    except Exception as e:
        logger.error(f"Error getting bracket info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coins/{address}/next-bracket-id")
async def get_next_bracket_id(address: str, current_profile: Profile = Depends(get_current_profile)):
    """Get the next available bracket_id for a coin"""
    try:
        coin = db_manager.get_coin_by_address(address)
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin with address {address} not found")
        
        next_bracket_id = db_manager.get_next_bracket_id(coin.id, current_profile.name)
        
        if next_bracket_id is None:
            return {
                "success": False,
                "message": "All bracket IDs (1-4) are currently in use for this coin",
                "next_bracket_id": None
            }
        
        return {
            "success": True,
            "next_bracket_id": next_bracket_id,
            "message": f"Next available bracket ID is {next_bracket_id}"
        }
        
    except Exception as e:
        logger.error(f"Error getting next bracket ID: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# New bracket-based endpoints
@router.post("/auto-multi-order")
async def create_auto_multi_order(
    address: str,
    strategy_number: int,
    order_type: str,
    total_amount: float,
    current_profile: Profile = Depends(get_current_profile)
):
    """Create multiple orders automatically using bracket configuration"""
    try:
        logger.info(f"Auto multi-order request for address: {address} using profile: {current_profile.name}")
        
        # Validate order type
        if order_type.upper() not in ["BUY", "SELL"]:
            raise HTTPException(status_code=400, detail="Order type must be 'BUY' or 'SELL'")
        
        # Validate total amount
        if total_amount <= 0:
            raise HTTPException(status_code=400, detail="Total amount must be greater than 0")
        
        # Create multi-order using bracket configuration
        result = db_manager.create_multi_order_with_bracket_config(
            address=address,
            strategy_number=strategy_number,
            order_type=order_type.upper(),
            profile_name=current_profile.name,
            total_amount=total_amount
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Successfully created {result['total_orders_created']} orders using bracket configuration",
                "coin": CoinResponse.from_orm(result["coin"]),
                "orders": [OrderResponse.from_orm(order) for order in result["orders"]],
                "total_orders_created": result["total_orders_created"],
                "total_amount": total_amount
            }
        else:
            raise HTTPException(status_code=500, detail="Auto multi-order creation failed")
            
    except ValueError as e:
        logger.error(f"Auto multi-order validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Auto multi-order creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coins/{address}/bracket-orders")
async def get_bracket_order_preview(
    address: str,
    total_amount: float,
    current_profile: Profile = Depends(get_current_profile)
):
    """Preview what orders would be created using bracket configuration"""
    try:
        # Get coin
        coin = db_manager.get_coin_by_address(address)
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin with address {address} not found")
        
        if not coin.market_cap:
            raise HTTPException(status_code=400, detail="Cannot preview orders: coin market cap is not available")
        
        # Calculate bracket
        from bracket_config import calculate_bracket
        bracket = calculate_bracket(coin.market_cap)
        
        # Get order parameters
        order_params = calculate_order_parameters(
            bracket=bracket,
            total_amount=total_amount,
            current_price=coin.current_price
        )
        
        # Get bracket info
        bracket_info = get_bracket_config_info(bracket)
        
        return {
            "success": True,
            "coin": CoinResponse.model_validate(coin),
            "bracket": bracket,
            "bracket_info": bracket_info,
            "total_amount": total_amount,
            "preview_orders": order_params
        }
        
    except Exception as e:
        logger.error(f"Error getting bracket order preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bracket-config")
async def get_bracket_config(current_profile: Profile = Depends(get_current_profile)):
    """Get the current bracket configuration"""
    try:
        from bracket_config import BRACKET_CONFIG, TRADE_SIZES, TAKE_PROFIT_PERCENTAGES, BRACKET_RANGES
        
        config = {
            "bracket_ranges": BRACKET_RANGES,
            "trade_sizes": TRADE_SIZES,
            "take_profit_percentages": TAKE_PROFIT_PERCENTAGES,
            "bracket_config": BRACKET_CONFIG
        }
        
        return {
            "success": True,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Error getting bracket config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# New bracket order placement endpoints
@router.post("/bracket-strategy")
async def execute_bracket_strategy(
    address: str,
    total_amount: float,
    bracket: Optional[int] = None,
    current_profile: Profile = Depends(get_current_profile)
):
    """Execute complete bracket strategy for a coin - places all 4 bracket orders"""
    try:
        logger.info(f"Bracket strategy execution request for address: {address} using profile: {current_profile.name}")
        
        # Validate total amount
        if total_amount <= 0:
            raise HTTPException(status_code=400, detail="Total amount must be greater than 0")
        
        # Validate bracket if provided
        if bracket is not None and bracket not in [1, 2, 3, 4, 5]:
            raise HTTPException(status_code=400, detail="Bracket must be between 1 and 5")
        
        # Execute bracket strategy
        result = bracket_order_manager.execute_bracket_strategy(
            profile_name=current_profile.name,
            address=address,
            total_amount=total_amount,
            bracket=bracket
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Bracket strategy executed successfully for {address}",
                "bracket": result["bracket"],
                "current_market_cap": result["current_market_cap"],
                "placed_orders": result["placed_orders"],
                "failed_orders": result["failed_orders"],
                "total_placed": result["total_placed"],
                "total_failed": result["total_failed"],
                "total_amount": total_amount,
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=500, detail=f"Bracket strategy execution failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Bracket strategy execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bracket-order-replace/{address}/{bracket_id}")
async def replace_bracket_order(
    address: str,
    bracket_id: int,
    new_amount: float,
    current_profile: Profile = Depends(get_current_profile)
):
    """Replace a specific bracket order with a new one"""
    try:
        logger.info(f"Replace bracket order request for {address}, bracket_id: {bracket_id}")
        
        # Validate bracket_id
        if not 1 <= bracket_id <= 4:
            raise HTTPException(status_code=400, detail="Bracket ID must be between 1 and 4")
        
        # Validate amount
        if new_amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")
        
        # Replace bracket order (original_bracket is handled internally by the manager)
        result = bracket_order_manager.replace_order(
            profile_name=current_profile.name,
            address=address,
            bracket_id=bracket_id,
            new_amount=new_amount
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Bracket order {bracket_id} replaced successfully",
                "order": result["order"],
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=500, detail=f"Bracket order replacement failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Bracket order replacement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bracket-preview/{address}")
async def get_bracket_strategy_preview(
    address: str,
    total_amount: float,
    current_profile: Profile = Depends(get_current_profile)
):
    """Preview bracket orders that would be placed without actually placing them"""
    try:
        logger.info(f"Bracket preview request for address: {address}")
        
        # Validate total amount
        if total_amount <= 0:
            raise HTTPException(status_code=400, detail="Total amount must be greater than 0")
        
        # Get bracket preview
        preview = bracket_order_manager.get_bracket_preview(
            address=address,
            total_amount=total_amount,
            profile_name=current_profile.name
        )
        
        if preview["success"]:
            return {
                "success": True,
                "message": f"Bracket preview generated for {address}",
                "bracket": preview["bracket"],
                "bracket_info": preview["bracket_info"],
                "current_market_cap": preview["current_market_cap"],
                "total_amount": preview["total_amount"],
                "orders": preview["orders"],
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=500, detail=f"Bracket preview failed: {preview['error']}")
            
    except Exception as e:
        logger.error(f"Bracket preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market-cap/{address}")
async def get_current_market_cap(
    address: str,
    current_profile: Profile = Depends(get_current_profile)
):
    """Get current market cap for a token"""
    try:
        logger.info(f"Market cap request for address: {address}")
        
        # Search for the address first to ensure we have current data
        search_success = bullx_automator.search_address(current_profile.name, address)
        if not search_success:
            raise HTTPException(status_code=500, detail="Failed to search for token")
        
        # Get current market cap
        market_cap = bullx_automator.get_market_cap(current_profile.name)
        if market_cap <= 0:
            raise HTTPException(status_code=500, detail="Failed to get market cap")
        
        # Calculate bracket
        from bracket_config import calculate_bracket
        bracket = calculate_bracket(market_cap)
        bracket_info = get_bracket_config_info(bracket)
        
        return {
            "success": True,
            "address": address,
            "market_cap": market_cap,
            "bracket": bracket,
            "bracket_info": bracket_info,
            "profile": current_profile.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Market cap retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-orders")
async def check_orders(current_profile: Profile = Depends(get_current_profile)):
    """Check all orders using enhanced processing with TP detection and renewal"""
    try:
        # Import and use the enhanced background tasks function directly
        from background_tasks import check_orders_enhanced_for_profile
        
        logger.info(f"API enhanced order check request for profile: {current_profile.name}")
        
        # Use the enhanced order processing function
        result = await check_orders_enhanced_for_profile(current_profile.name)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Enhanced order check completed for {current_profile.name}",
                "profile": current_profile.name,
                "orders_checked": result.get("orders_checked", 0),
                "orders_marked_for_renewal": result.get("orders_marked_for_renewal", 0),
                "orders_replaced": result.get("orders_replaced", 0),
                "summary": result.get("summary", "")
            }
        else:
            raise HTTPException(status_code=500, detail=f"Enhanced order check failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Enhanced order check API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def calculate_strategy_prices(strategy_number: int, market_cap: float, order_type: str) -> dict:
    """Calculate default prices based on strategy and market cap"""
    # This is a basic implementation - you can customize based on your strategies
    
    base_price = 1.0  # This should be the current token price (you'll need to implement price fetching)
    
    if strategy_number == 1:  # Conservative
        if order_type.upper() == "BUY":
            entry_price = base_price * 0.98  # Buy 2% below current price
            take_profit = base_price * 1.05  # 5% profit
            stop_loss = base_price * 0.95    # 5% loss
        else:  # SELL
            entry_price = base_price * 1.02  # Sell 2% above current price
            take_profit = base_price * 0.95  # 5% profit (price goes down)
            stop_loss = base_price * 1.05    # 5% loss (price goes up)
    
    elif strategy_number == 2:  # Aggressive
        if order_type.upper() == "BUY":
            entry_price = base_price * 0.95  # Buy 5% below current price
            take_profit = base_price * 1.15  # 15% profit
            stop_loss = base_price * 0.90    # 10% loss
        else:  # SELL
            entry_price = base_price * 1.05  # Sell 5% above current price
            take_profit = base_price * 0.85  # 15% profit (price goes down)
            stop_loss = base_price * 1.10    # 10% loss (price goes up)
    
    elif strategy_number == 3:  # Market cap based
        if market_cap > 1000000:  # > 1M market cap
            multiplier = 0.5  # More conservative for larger market cap
        else:
            multiplier = 1.5  # More aggressive for smaller market cap
        
        if order_type.upper() == "BUY":
            entry_price = base_price * (1 - 0.03 * multiplier)
            take_profit = base_price * (1 + 0.08 * multiplier)
            stop_loss = base_price * (1 - 0.06 * multiplier)
        else:  # SELL
            entry_price = base_price * (1 + 0.03 * multiplier)
            take_profit = base_price * (1 - 0.08 * multiplier)
            stop_loss = base_price * (1 + 0.06 * multiplier)
    
    else:  # Default strategy
        if order_type.upper() == "BUY":
            entry_price = base_price * 0.97
            take_profit = base_price * 1.10
            stop_loss = base_price * 0.93
        else:  # SELL
            entry_price = base_price * 1.03
            take_profit = base_price * 0.90
            stop_loss = base_price * 1.07
    
    return {
        'entry_price': round(entry_price, 6),
        'take_profit': round(take_profit, 6),
        'stop_loss': round(stop_loss, 6)
    }

# Background Task Health Monitoring Endpoints
@router.get("/background-tasks/health")
async def get_background_task_health(
    profile_name: Optional[str] = Query(None, description="Get health for specific profile"),
    current_profile: Profile = Depends(get_current_profile)
):
    """Get health status of background tasks"""
    try:
        # If no profile specified, use current profile
        target_profile = profile_name or current_profile.name
        
        health_status = get_background_task_health(target_profile)
        
        return {
            "success": True,
            "health_status": health_status,
            "requested_profile": target_profile
        }
        
    except Exception as e:
        logger.error(f"Error getting background task health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/background-tasks/history/{profile_name}")
async def get_background_task_history(
    profile_name: str,
    limit: int = Query(20, description="Number of recent tasks to return", ge=1, le=100),
    current_profile: Profile = Depends(get_current_profile)
):
    """Get task execution history for a profile"""
    try:
        # Validate profile access (users can only see their own profile or if they're admin)
        if profile_name != current_profile.name:
            # For now, allow access to both profiles - you might want to add admin check here
            if profile_name not in ["Saruman", "Gandalf"]:
                raise HTTPException(status_code=403, detail="Access denied to this profile")
        
        history = get_task_execution_history(profile_name, limit)
        
        return {
            "success": True,
            "profile_name": profile_name,
            "history": history,
            "total_returned": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task execution history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/background-tasks/start/{profile_name}")
async def start_background_monitoring(
    profile_name: str,
    current_profile: Profile = Depends(get_current_profile)
):
    """Start background task monitoring for a specific profile"""
    try:
        # Validate profile access
        if profile_name != current_profile.name:
            if profile_name not in ["Saruman", "Gandalf"]:
                raise HTTPException(status_code=403, detail="Access denied to this profile")
        
        await start_background_tasks_for_profile(profile_name)
        
        return {
            "success": True,
            "message": f"Background monitoring started for profile: {profile_name}",
            "profile_name": profile_name
        }
        
    except Exception as e:
        logger.error(f"Error starting background monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/background-tasks/stop/{profile_name}")
async def stop_background_monitoring(
    profile_name: str,
    current_profile: Profile = Depends(get_current_profile)
):
    """Stop background task monitoring for a specific profile"""
    try:
        # Validate profile access
        if profile_name != current_profile.name:
            if profile_name not in ["Saruman", "Gandalf"]:
                raise HTTPException(status_code=403, detail="Access denied to this profile")
        
        await stop_background_tasks_for_profile(profile_name)
        
        return {
            "success": True,
            "message": f"Background monitoring stopped for profile: {profile_name}",
            "profile_name": profile_name
        }
        
    except Exception as e:
        logger.error(f"Error stopping background monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/background-tasks/manual-check/{profile_name}")
async def manual_background_check(
    profile_name: str,
    current_profile: Profile = Depends(get_current_profile)
):
    """Manually trigger a background task check for a specific profile"""
    try:
        # Validate profile access
        if profile_name != current_profile.name:
            if profile_name not in ["Saruman", "Gandalf"]:
                raise HTTPException(status_code=403, detail="Access denied to this profile")
        
        # Trigger manual check using the enhanced monitor
        await enhanced_order_monitor._execute_monitored_task(profile_name)
        
        return {
            "success": True,
            "message": f"Manual background check completed for profile: {profile_name}",
            "profile_name": profile_name
        }
        
    except Exception as e:
        logger.error(f"Error in manual background check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/background-tasks/status")
async def get_background_tasks_status(current_profile: Profile = Depends(get_current_profile)):
    """Get overall status of background task system"""
    try:
        # Get health for all monitored profiles
        health_status = get_background_task_health()
        
        # Get additional system info
        system_status = {
            "scheduler_running": enhanced_order_monitor.is_running,
            "monitored_profiles": list(enhanced_order_monitor.monitored_profiles),
            "total_monitored_profiles": len(enhanced_order_monitor.monitored_profiles),
            "task_timeout_seconds": enhanced_order_monitor.task_timeout,
            "max_history_size": enhanced_order_monitor.max_history_size
        }
        
        return {
            "success": True,
            "system_status": system_status,
            "health_status": health_status
        }
        
    except Exception as e:
        logger.error(f"Error getting background tasks status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/background-tasks/missed-tasks/{profile_name}")
async def get_missed_tasks(
    profile_name: str,
    hours: int = Query(24, description="Look back this many hours for missed tasks", ge=1, le=168),
    current_profile: Profile = Depends(get_current_profile)
):
    """Get missed tasks for a profile within a time window"""
    try:
        # Validate profile access
        if profile_name != current_profile.name:
            if profile_name not in ["Saruman", "Gandalf"]:
                raise HTTPException(status_code=403, detail="Access denied to this profile")
        
        # Get task history
        history = get_task_execution_history(profile_name, limit=100)
        
        # Filter for missed tasks within the time window
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        missed_tasks = []
        for task in history:
            if task.get("missed", False):
                task_time = datetime.fromisoformat(task["scheduled_time"])
                if task_time >= cutoff_time:
                    missed_tasks.append(task)
        
        return {
            "success": True,
            "profile_name": profile_name,
            "hours_looked_back": hours,
            "missed_tasks": missed_tasks,
            "total_missed": len(missed_tasks)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting missed tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Clear database endpoints
@router.delete("/coins/{address}")
async def clear_coin_data(
    address: str,
    clear_orders_only: bool = Query(False, description="If true, only clear orders. If false, clear coin and all its orders"),
    current_profile: Profile = Depends(get_current_profile)
):
    """Clear coin data and/or orders from database"""
    try:
        logger.info(f"Clear coin data request for address: {address}, orders_only: {clear_orders_only}, profile: {current_profile.name}")
        
        result = db_manager.clear_coin_data(
            address=address,
            profile_name=current_profile.name,
            orders_only=clear_orders_only
        )
        
        if result["success"]:
            action = "orders cleared" if clear_orders_only else "coin and orders cleared"
            return {
                "success": True,
                "message": f"Successfully {action} for coin {address}",
                "orders_cleared": result["orders_cleared"],
                "coin_removed": result.get("coin_removed", False),
                "profile": current_profile.name
            }
        else:
            raise HTTPException(status_code=404, detail=f"Coin with address {address} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear coin data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-all-data")
async def clear_all_data(
    current_profile: Profile = Depends(get_current_profile)
):
    """Clear all coins and orders for the current profile"""
    try:
        logger.info(f"Clear all data request for profile: {current_profile.name}")
        
        result = db_manager.clear_all_profile_data(current_profile.name)
        
        return {
            "success": True,
            "message": f"Successfully cleared all data for profile {current_profile.name}",
            "coins_cleared": result["coins_cleared"],
            "orders_cleared": result["orders_cleared"],
            "profile": current_profile.name
        }
        
    except Exception as e:
        logger.error(f"Clear all data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
