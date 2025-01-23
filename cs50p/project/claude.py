from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchElementException,
    TimeoutException,
)
import schedule
import time
import os
import yagmail
import json
import logging
from dotenv import load_dotenv
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class UserCredentials:
    username: str
    password: str
    name: str


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""

    pass


class InternetUsageMonitor:
    def __init__(self):
        self.setup_logging()
        self.load_configuration()
        self.current_index = 0

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("internet_monitor.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def load_configuration(self):
        """Load and validate all configuration from environment variables."""
        load_dotenv()

        try:
            ids_json = os.getenv("IDS_JSON")
            if not ids_json:
                raise ConfigurationError("IDS_JSON is not set in the .env file")

            raw_users = json.loads(ids_json)
            self.users = [UserCredentials(**user) for user in raw_users]

            self.router_password = os.getenv("ROUTER_PASS")
            self.email_user = os.getenv("EMAIL_USER")
            self.email_password = os.getenv("EMAIL_PASS")
            self.threshold_usage = int(os.getenv("THRESHOLD_USAGE", "11600"))
            self.email_recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")
            self.driver_path = os.getenv("DRIVER_PATH", "/usr/local/bin/geckodriver")

            if not all([self.email_user, self.email_password, self.email_recipients]):
                raise ConfigurationError("Email configuration is incomplete")

        except (json.JSONDecodeError, ValueError) as e:
            raise ConfigurationError(f"Configuration error: {str(e)}")

    def get_driver(self) -> webdriver.Firefox:
        """Create and return a configured webdriver instance."""
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")  # Run in headless mode
        service = Service(self.driver_path)
        return webdriver.Firefox(service=service, options=options)

    def wait_and_find_element(
        self, driver: webdriver.Firefox, by: By, value: str, timeout: int = 10
    ):
        """Wait for and return an element, with proper error handling."""
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.error(f"Timeout waiting for element: {value}")
            raise

    def change_user(self, user: UserCredentials) -> bool:
        """Change the router user credentials."""
        driver = self.get_driver()
        try:
            driver.get("http://192.168.0.1")

            password_field = self.wait_and_find_element(driver, By.ID, "pcPassword")
            password_field.send_keys(self.router_password)

            login_button = self.wait_and_find_element(driver, By.ID, "loginBtn")
            login_button.click()

            driver.switch_to.frame("frame1")
            network_menu = self.wait_and_find_element(driver, By.ID, "menu_network")
            network_menu.click()

            driver.switch_to.default_content()
            driver.switch_to.frame("frame2")

            # Update credentials
            username_field = self.wait_and_find_element(driver, By.ID, "username")
            password_field = self.wait_and_find_element(driver, By.ID, "pwd")
            confirm_field = self.wait_and_find_element(driver, By.ID, "pwd2")

            driver.execute_script("arguments[0].value = '';", username_field)
            username_field.send_keys(user.username)

            driver.execute_script("arguments[0].value = '';", password_field)
            password_field.send_keys(user.password)

            driver.execute_script("arguments[0].value = '';", confirm_field)
            confirm_field.send_keys(user.password)

            save_button = self.wait_and_find_element(driver, By.ID, "saveBtn")
            save_button.click()

            self.logger.info(f"Successfully changed user to {user.name}")
            return True

        except Exception as e:
            self.logger.error(f"Error changing user to {user.name}: {str(e)}")
            self.send_email(
                "Change User Error", f"Error changing user to {user.name}: {str(e)}"
            )
            return False

        finally:
            driver.quit()

    def check_status(self, user: UserCredentials) -> Optional[int]:
        """Check the usage status for a given user."""
        driver = self.get_driver()
        try:
            driver.get("http://10.220.20.12/index.php/home/login")

            username_field = self.wait_and_find_element(driver, By.ID, "username")
            username_field.send_keys(user.username)

            password_field = self.wait_and_find_element(driver, By.ID, "password")
            password_field.send_keys(user.password)

            sign_in = self.wait_and_find_element(
                driver, By.XPATH, "//button[text()='Sign In']"
            )
            sign_in.click()

            usage_element = self.wait_and_find_element(
                driver,
                By.XPATH,
                "(//td[contains(normalize-space(text()), 'Minute')])[1]",
            )

            usage = int(usage_element.text.split(" ")[0])
            self.logger.info(f"Usage for {user.name}: {usage} minutes")
            return usage

        except Exception as e:
            self.logger.error(f"Error checking status for {user.name}: {str(e)}")
            self.send_email(
                "Check Status Error", f"Error checking status for {user.name}: {str(e)}"
            )
            return None

        finally:
            driver.quit()

    def send_email(self, subject: str, body: str):
        """Send email notification."""
        try:
            yag = yagmail.SMTP(self.email_user, self.email_password)
            yag.send(to=self.email_recipients, subject=subject, contents=body)
            self.logger.info(f"Email sent successfully: {subject}")
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")

    def run(self):
        """Main execution loop."""
        while True:
            current_user = self.users[self.current_index]
            usage = self.check_status(current_user)

            if usage is None:
                self.logger.error("Unable to fetch usage. Retrying in 5 minutes.")
                time.sleep(300)
                continue

            if usage > self.threshold_usage:
                self.logger.info(f"Usage threshold exceeded for {current_user.name}")
                self.current_index = (self.current_index + 1) % len(self.users)
                new_user = self.users[self.current_index]

                if self.change_user(new_user):
                    self.send_email(
                        "User Changed",
                        f"Switched from {current_user.name} to {new_user.name} due to usage threshold",
                    )
                continue

            minutes_remaining = self.threshold_usage - usage
            self.logger.info(f"Scheduling next check in {minutes_remaining} minutes")
            time.sleep(minutes_remaining * 60)


if __name__ == "__main__":
    monitor = InternetUsageMonitor()
    monitor.run()
