import os
import sys
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


def _chrome_profile_path(profile_name: str) -> str:
    """Return the Chrome profile path appropriate for the current OS."""
    if sys.platform == "win32":
        return os.path.expanduser(
            rf"~\AppData\Local\Google\Chrome\User Data\{profile_name}"
        )
    elif sys.platform == "darwin":
        return os.path.expanduser(
            f"~/Library/Application Support/Google/Chrome/{profile_name}"
        )
    else:
        # Linux
        return os.path.expanduser(
            f"~/.config/google-chrome/{profile_name}"
        )


# Base directory for resolving relative paths
_BASE_DIR = Path(__file__).parent


# Application configuration
class Config:
    # Database - absolute path anchored to project directory
    DATABASE_URL = f"sqlite:///{_BASE_DIR / 'bullx_auto.db'}"

    # API Configuration
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_RELOAD = False  # Disabled: auto-reload causes issues with log/db file changes

    # Chrome profiles configuration
    CHROME_PROFILES = {
        "Saruman": _chrome_profile_path("Profile Saruman"),
        "Gandalf": _chrome_profile_path("Profile Gandalf"),
    }

    # CORS configuration
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000"
    ).split(",")
    
    # BullX configuration
    BULLX_BASE_URL = "https://neo.bullx.io"
    
    # Order monitoring
    ORDER_CHECK_INTERVAL_MINUTES = 5
    
    # Logging
    LOG_LEVEL = "INFO"

    # Application start time (set by main.py at startup)
    APP_START_TIME = None

    # Daily health check reports
    REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "reports")
    HEALTH_CHECK_HOUR = 7   # Hour to run the daily check (24h format)
    HEALTH_CHECK_MINUTE = 0  # Minute to run the daily check
    
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
    API_RELOAD = False  # Disabled: reload causes route registration issues with newer modules

class ProductionConfig(Config):
    DEBUG = False
    API_RELOAD = False
    LOG_LEVEL = "WARNING"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []

# Get configuration based on environment
def get_config() -> Config:
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionConfig()
    else:
        return DevelopmentConfig()

# Global config instance
config = get_config()
