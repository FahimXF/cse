import logging
import json
import os
import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Optional, List, Dict, Any

import schedule
import yagmail
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchElementException

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("router_manager.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class UserConfig:
    """Data class to hold user configuration information."""

    username: str
    password: str
    name: str


def retry_on_exception(retries: int = 3, delay: int = 5):
    """Decorator to retry functions on exception with delay."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        logger.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
            return None

        return wrapper

    return decorator


class RouterManager:
    def __init__(self, config_path: str = ".env"):
        """Initialize RouterManager with configuration."""
        self.config_path = config_path
        self.current_index = 0
        self._load_config()
        self._setup_driver_config()

    def _load_config(self) -> None:
        """Load and validate configuration from .env file."""
        load_dotenv(self.config_path)
        try:
            ids_json = os.getenv("IDS_JSON")
            if not ids_json:
                raise ValueError("IDS_JSON is not set in the .env file.")

            raw_ids = json.loads(ids_json)
            self.users = [UserConfig(**user) for user in raw_ids]

            self.router_pass = os.getenv("ROUTER_PASS")
            self.email_user = os.getenv("EMAIL_USER")
            self.email_pass = os.getenv("EMAIL_PASS")
            self.threshold_usage = int(os.getenv("THRESHOLD_USAGE", "11600"))
            self.email_recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")

            # Validate required fields
            if not all([self.email_user, self.email_pass, self.router_pass]):
                raise ValueError("Missing required environment variables")
            if not self.email_recipients or self.email_recipients == [""]:
                raise ValueError("EMAIL_RECIPIENTS must be set in the .env file")

            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            raise

    def _setup_driver_config(self) -> None:
        """Set up Firefox driver configuration."""
        self.options = Options()
        # self.options.add_argument("--headless")
        # self.options.add_argument("--no-sandbox")
        # self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--width=1920")
        self.options.add_argument("--height=1080")

        # Set up geckodriver service
        geckodriver_path = "/usr/local/bin/geckodriver"
        if not Path(geckodriver_path).exists():
            raise FileNotFoundError(f"Geckodriver not found at {geckodriver_path}")
        self.service = Service(geckodriver_path)

    def get_driver(self):
        """Create and return a configured Firefox WebDriver instance."""
        return webdriver.Firefox(service=self.service, options=self.options)

    @retry_on_exception(retries=3, delay=5)
    def fetch_current_user(self) -> Optional[UserConfig]:
        """Fetch current router user configuration."""
        driver = self.get_driver()
        try:
            driver.get("http://192.168.0.1")
            wait = WebDriverWait(driver, 10)

            # Login to router
            password_field = wait.until(
                EC.presence_of_element_located((By.ID, "pcPassword"))
            )
            password_field.send_keys(self.router_pass)
            driver.find_element(By.ID, "loginBtn").click()

            # Navigate to network settings
            driver.switch_to.frame("frame1")
            wait.until(EC.element_to_be_clickable((By.ID, "menu_network"))).click()
            driver.switch_to.default_content()
            driver.switch_to.frame("frame2")

            # Get current username
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            current_username = username_field.get_attribute("value")

            # Find matching user
            for user in self.users:
                if user.username == current_username:
                    return user

            logger.warning("No matching user found")
            return None

        except Exception as e:
            logger.error(f"Error in fetch_current_user: {e}")
            self.send_email("Router Manager Error", f"Error fetching current user: {e}")
            raise
        finally:
            driver.quit()

    @retry_on_exception(retries=3, delay=5)
    def change_user(self, user: UserConfig) -> bool:
        """Change router user to specified user."""
        driver = self.get_driver()
        try:
            driver.get("http://192.168.0.1")
            wait = WebDriverWait(driver, 10)

            # Login to router
            password_field = wait.until(
                EC.presence_of_element_located((By.ID, "pcPassword"))
            )
            password_field.send_keys(self.router_pass)
            driver.find_element(By.ID, "loginBtn").click()

            # Navigate to network settings
            driver.switch_to.frame("frame1")
            wait.until(EC.element_to_be_clickable((By.ID, "menu_network"))).click()
            driver.switch_to.default_content()
            driver.switch_to.frame("frame2")

            # Update user credentials
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = driver.find_element(By.ID, "pwd")
            confirm_field = driver.find_element(By.ID, "pwd2")

            # Clear and set new values
            for field in [username_field, password_field, confirm_field]:
                driver.execute_script("arguments[0].value = '';", field)

            username_field.send_keys(user.username)
            password_field.send_keys(user.password)
            confirm_field.send_keys(user.password)

            # Save changes
            driver.find_element(By.ID, "saveBtn").click()
            logger.info(f"Successfully changed user to {user.name}")
            return True

        except Exception as e:
            logger.error(f"Error in change_user: {e}")
            self.send_email(
                "Router Manager Error", f"Error changing user to {user.name}: {e}"
            )
            raise
        finally:
            driver.quit()

    @retry_on_exception(retries=3, delay=5)
    def check_status(self, user: UserConfig) -> Optional[int]:
        """Check usage status for specified user."""
        driver = self.get_driver()
        try:
            driver.get("http://10.220.20.12/index.php/home/login")
            wait = WebDriverWait(driver, 10)

            # Login
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.send_keys(user.username)
            driver.find_element(By.ID, "password").send_keys(user.password)
            driver.find_element(By.XPATH, "//button[text()='Sign In']").click()

            # Get usage
            usage_element = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "(//td[contains(normalize-space(text()), 'Minute')])[1]")
                )
            )
            usage = int(usage_element.text.split(" ")[0])

            logger.info(f"Usage for {user.name}: {usage} minutes")
            return usage

        except Exception as e:
            logger.error(f"Error in check_status: {e}")
            self.send_email(
                "Router Manager Error", f"Error checking status for {user.name}: {e}"
            )
            raise
        finally:
            driver.quit()

    def send_email(self, subject: str, body: str) -> None:
        """Send email notification."""
        try:
            yag = yagmail.SMTP(self.email_user, self.email_pass)
            yag.send(to=self.email_recipients, subject=subject, contents=body)
            logger.info(f"Email sent successfully: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

    def run(self) -> None:
        """Main execution loop."""
        try:
            # Initial check
            current_user = self.fetch_current_user()
            if current_user is None:
                logger.error("Unable to fetch the current user. Exiting.")
                return

            usage = self.check_status(current_user)
            if usage is None:
                logger.error("Unable to fetch usage. Exiting.")
                return

            if usage > self.threshold_usage:
                self.current_index = (self.current_index + 1) % len(self.users)
                self.change_user(self.users[self.current_index])
            else:
                remaining_minutes = self.threshold_usage - usage
                logger.info(f"Scheduling next check in {remaining_minutes} minutes")

                schedule.every(remaining_minutes).minutes.do(self.run)
                try:
                    while True:
                        schedule.run_pending()
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Shutting down gracefully...")
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    raise

        except Exception as e:
            logger.error(f"Error in main execution: {e}")
            self.send_email(
                "Router Manager Critical Error",
                f"Critical error in main execution: {e}",
            )
            raise


if __name__ == "__main__":
    try:
        manager = RouterManager()
        manager.run()
    except Exception as e:
        logger.error(f"Failed to start RouterManager: {e}")
        raise
