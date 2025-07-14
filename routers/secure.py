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
        db_manager.get_coin_by_address(request.address)
        if success:
            return {
                "success": True,
                "message": f"Successfully searched for address: {request.address}",
                "coin_data" : db_manager.get_coin_by_address(request.address),
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
async def get_bracket_info(current_profile: Profile = Depends(get_current_profile)):
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
