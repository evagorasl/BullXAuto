import os
from typing import Dict, Any

# Application configuration
class Config:
    # Database
    DATABASE_URL = "sqlite:///./bullx_auto.db"
    
    # API Configuration
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_RELOAD = True
    
    # Chrome profiles configuration
    CHROME_PROFILES = {
        "Saruman": os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Profile Saruman"),
        "Gandalf": os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Profile Gandalf")
    }
    
    # BullX configuration
    BULLX_BASE_URL = "https://neo.bullx.io"
    
    # Order monitoring
    ORDER_CHECK_INTERVAL_MINUTES = 5
    
    # Logging
    LOG_LEVEL = "INFO"
    
    # Default strategy parameters
    DEFAULT_STRATEGIES = {
        1: {  # Conservative
            "name": "Conservative",
            "description": "Low risk, moderate returns",
            "buy": {
                "entry_offset": -0.02,  # Buy 2% below current price
                "take_profit_offset": 0.05,  # 5% profit
                "stop_loss_offset": -0.05   # 5% loss
            },
            "sell": {
                "entry_offset": 0.02,   # Sell 2% above current price
                "take_profit_offset": -0.05,  # 5% profit (price goes down)
                "stop_loss_offset": 0.05    # 5% loss (price goes up)
            }
        },
        2: {  # Aggressive
            "name": "Aggressive",
            "description": "High risk, high returns",
            "buy": {
                "entry_offset": -0.05,  # Buy 5% below current price
                "take_profit_offset": 0.15,  # 15% profit
                "stop_loss_offset": -0.10   # 10% loss
            },
            "sell": {
                "entry_offset": 0.05,   # Sell 5% above current price
                "take_profit_offset": -0.15,  # 15% profit (price goes down)
                "stop_loss_offset": 0.10    # 10% loss (price goes up)
            }
        },
        3: {  # Market Cap Based
            "name": "Market Cap Based",
            "description": "Adjusts based on market capitalization",
            "large_cap_threshold": 1000000,  # 1M market cap threshold
            "large_cap_multiplier": 0.5,     # More conservative for large cap
            "small_cap_multiplier": 1.5,     # More aggressive for small cap
            "buy": {
                "entry_offset": -0.03,
                "take_profit_offset": 0.08,
                "stop_loss_offset": -0.06
            },
            "sell": {
                "entry_offset": 0.03,
                "take_profit_offset": -0.08,
                "stop_loss_offset": 0.06
            }
        }
    }

# Environment-specific configurations
class DevelopmentConfig(Config):
    DEBUG = True
    API_RELOAD = True

class ProductionConfig(Config):
    DEBUG = False
    API_RELOAD = False
    LOG_LEVEL = "WARNING"

# Get configuration based on environment
def get_config() -> Config:
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionConfig()
    else:
        return DevelopmentConfig()

# Global config instance
config = get_config()
