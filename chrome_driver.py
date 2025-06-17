from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager as WebDriverManager
from database import db_manager
import time
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChromeDriverManager:
    def __init__(self):
        self.drivers = {}  # Store active drivers by profile name
    
    def get_driver(self, profile_name: str):
        """Get or create a Chrome driver for the specified profile"""
        if profile_name in self.drivers:
            return self.drivers[profile_name]
        
        # Get profile from database
        profile = db_manager.get_profile_by_name(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(f"--user-data-dir={profile.chrome_profile_path}")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-search-engine-choice-screen")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36')
        #chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(
            service=ChromeService(WebDriverManager().install()), 
            options=chrome_options
        )

        self.drivers[profile_name] = driver
        return driver
    
    def close_driver(self, profile_name: str):
        """Close driver for specific profile"""
        if profile_name in self.drivers:
            self.drivers[profile_name].quit()
            del self.drivers[profile_name]
    
    def close_all_drivers(self):
        """Close all active drivers"""
        for profile_name in list(self.drivers.keys()):
            self.close_driver(profile_name)

class BullXAutomator:
    def __init__(self, driver_manager: ChromeDriverManager):
        self.driver_manager = driver_manager
        self.base_url = "https://neo.bullx.io"
    
    def _ensure_logged_in(self, profile_name: str) -> bool:
        """Internal method to ensure we're logged in before performing operations"""
        try:
            # Check if profile is already logged in according to database
            profile = db_manager.get_profile_by_name(profile_name)
            if profile and profile.is_logged_in:
                # We assume it's logged in, but we'll verify by checking the page
                driver = self.driver_manager.get_driver(profile_name)
                
                # If we're not on BullX, navigate there
                if "neo.bullx.io" not in driver.current_url:
                    driver.get(self.base_url)
                
                # Check if we're logged in by looking for a specific element
                try:
                    # Wait for a short time to see if we're logged in
                    WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.XPATH, "//div[text()='Connect Telegram']"))
                    )
                    # Not logged in, proceed with login
                    logger.info(f"Profile {profile_name} needs to log in")
                    db_manager.update_profile_login_status(profile_name, False)

                    pass
                except TimeoutException:
                    # Logged in already
                    logger.info(f"Profile {profile_name} is already logged in")
                    db_manager.update_profile_login_status(profile_name, True)

                    return True
            
            # Not logged in, perform login
            driver = self.driver_manager.get_driver(profile_name)
            driver.get(self.base_url)
            print(1)
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            try:
                connect_telegram = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, "//div[text()='Connect Telegram']"))
                )
            except:
                logger.info(f"Already logged in.")
                # Update login status in database
                db_manager.update_profile_login_status(profile_name, True)
            else:
                db_manager.update_profile_login_status(profile_name, False)

                logger.info(f"Opened BullX for profile {profile_name}. Please complete login manually.")
                # Check if already logged in by looking for specific elements
                connect_telegram.click()
                WebDriverWait(driver, 300).until(
                    EC.title_contains("Neo Vision")
                ) # Give time for page to fully load
            
            logger.info(f"Successfully logged in.")
            # Update login status in database
            db_manager.update_profile_login_status(profile_name, True)
            
            return True
            
        except Exception as e:
            logger.error(f"Login failed for profile {profile_name}: {e}")
            return False
    
    def login(self, profile_name: str) -> bool:
        """Open browser and navigate to BullX for login (API endpoint)"""
        return self._ensure_logged_in(profile_name)
    
    def search_address(self, profile_name: str, address: str) -> bool:
        """Search for a specific address/token and store coin information"""
        try:
            # Ensure we're logged in first
            if not self._ensure_logged_in(profile_name):
                return False
                
            driver = self.driver_manager.get_driver(profile_name)
            
            # Look for search bar
            search_bar = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Search']")))
            search_bar.click()
            # Look for search input
            search_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Search']")))

            # Enter address to search
            search_input.clear()
            search_input.send_keys(address)
            
            # Wait for results
            results = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.XPATH, "//div[@id='search-results-list']/div/a[contains(@href, '/terminal?')]")))
            logger.info(f"Successfully searched for address: {address}")

            WebDriverWait(driver, 15).until(EC.element_to_be_clickable(results[0]))
            results[0].click()
            logger.info(f"Clicked first result.")
            
            # Extract coin information
            coin_data = self._extract_coin_data(driver, address)
            
            # Store coin information in database
            if coin_data:
                db_manager.create_or_update_coin(address, coin_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Search failed for address {address}: {e}")
            return False, {}
    
    def _extract_coin_data(self, driver, address: str) -> dict:
        """Extract coin information from the page"""
        try:
            coin_data = {
                "address": address,
                "url": driver.current_url
            }
            
            # Try to extract coin name
            try:
                # Look for name element - adjust selector based on actual BullX UI
                name_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='root']/div[1]/div[2]/main/div/div[1]/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/span/span[1]"))
                )
                coin_data["name"] = name_element.text.strip()
            except:
                logger.warning(f"Could not extract name for {address}")
            
            # Extract market cap
            market_cap = self.get_market_cap(None, driver=driver)
            if market_cap > 0:
                coin_data["market_cap"] = market_cap
            
            # Try to extract current price
            try:
                # Look for price element - adjust selector based on actual BullX UI
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div/span[text()='Price']"))
                )
                price_element = price_element.find_element(By.XPATH, "../span[2]")
                price_text = price_element.text.strip().replace('$', '').replace(',', '')
                def replaceSubScript(text):
                                text = text.replace(u"\u2081", "")
                                text = text.replace(u"\u2082", "0")
                                text = text.replace(u"\u2083", "00")
                                text = text.replace(u"\u2084", "000")
                                text = text.replace(u"\u2085", "0000")
                                text = text.replace(u"\u2086", "00000")
                                text = text.replace(u"\u2087", "000000")
                                text = text.replace(u"\u2088", "0000000")
                                text = text.replace(u"\u2089", "00000000")
                                return text
                price_text = replaceSubScript(price_text)
                coin_data["current_price"] = float(price_text)
            except Exception as e:
                logger.warning(f"Could not extract price for {address}: {e}")
            
            return coin_data
            
        except Exception as e:
            logger.error(f"Error extracting coin data: {e}")
            return {"address": address}
    
    def get_market_cap(self, profile_name: str = None, driver = None) -> float:
        """Get current market cap of the selected token"""
        try:
            # If driver is not provided, get it from profile_name
            if driver is None:
                if profile_name is None:
                    logger.error("Either profile_name or driver must be provided")
                    return 0.0
                    
                # Ensure we're logged in first
                if not self._ensure_logged_in(profile_name):
                    return 0.0
                    
                driver = self.driver_manager.get_driver(profile_name)
            
            # Look for market cap element - adjust selector based on actual BullX UI
            market_cap_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div/span[text()='Mkt Cap']"))
            )
            market_cap_value = market_cap_element.find_element(By.XPATH, "../span[2]")
            
            market_cap_text = market_cap_value.text
            # Parse market cap value (remove $ and convert K/M/B to numbers)
            market_cap = self._parse_market_cap(market_cap_text)
            
            return market_cap
            
        except Exception as e:
            logger.error(f"Failed to get market cap: {e}")
            return 0.0
    
    def _parse_market_cap(self, market_cap_text: str) -> float:
        """Parse market cap text to float value"""
        try:
            # Remove $ and spaces
            text = market_cap_text.replace('$', '').replace(',', '').strip()
            
            # Handle K, M, B suffixes
            if text.endswith('K'):
                return float(text[:-1]) * 1000
            elif text.endswith('M'):
                return float(text[:-1]) * 1000000
            elif text.endswith('B'):
                return float(text[:-1]) * 1000000000
            else:
                return float(text)
                
        except ValueError:
            logger.error(f"Could not parse market cap: {market_cap_text}")
            return 0.0
    
    def execute_strategy(self, profile_name: str, strategy_number: int, address: str, 
                        order_type: str, entry_price: float, take_profit: float, 
                        stop_loss: float) -> bool:
        """Execute a trading strategy"""
        try:
            # Ensure we're logged in first
            if not self._ensure_logged_in(profile_name):
                return False
                
            # Search for the address
            if not self.search_address(profile_name, address):
                return False
            
            # Get market cap
            market_cap = self.get_market_cap(profile_name)
            
            driver = self.driver_manager.get_driver(profile_name)
            
            # Navigate to trading interface - adjust based on actual BullX UI
            trade_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".trade-button, [data-testid='trade']"))
            )
            trade_button.click()
            
            # Select BUY or SELL
            order_type_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, f"button[data-type='{order_type.lower()}']"))
            )
            order_type_button.click()
            
            # Enter trading parameters
            self._enter_trading_parameters(driver, entry_price, take_profit, stop_loss)
            
            # Place order
            place_order_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".place-order, [data-testid='place-order']"))
            )
            place_order_button.click()
            
            # Save order to database with coin relationship
            order_data = {
                "strategy_number": strategy_number,
                "order_type": order_type,
                "market_cap": market_cap,
                "entry_price": entry_price,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "profile_name": profile_name
            }
            
            db_manager.create_order_with_coin(address, order_data)
            
            logger.info(f"Successfully executed strategy {strategy_number} for {address}")
            return True
            
        except Exception as e:
            logger.error(f"Strategy execution failed: {e}")
            return False
    
    def _enter_trading_parameters(self, driver, entry_price: float, take_profit: float, stop_loss: float):
        """Enter trading parameters in the UI"""
        try:
            # Entry price
            entry_input = driver.find_element(By.CSS_SELECTOR, "input[name='entry'], input[placeholder*='price']")
            entry_input.clear()
            entry_input.send_keys(str(entry_price))
            
            # Take profit
            tp_input = driver.find_element(By.CSS_SELECTOR, "input[name='take-profit'], input[placeholder*='profit']")
            tp_input.clear()
            tp_input.send_keys(str(take_profit))
            
            # Stop loss
            sl_input = driver.find_element(By.CSS_SELECTOR, "input[name='stop-loss'], input[placeholder*='loss']")
            sl_input.clear()
            sl_input.send_keys(str(stop_loss))
            
        except Exception as e:
            logger.error(f"Failed to enter trading parameters: {e}")
            raise

# Global driver manager instance
chrome_driver_manager = ChromeDriverManager()
bullx_automator = BullXAutomator(chrome_driver_manager)
