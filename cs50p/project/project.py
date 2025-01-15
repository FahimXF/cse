from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import schedule
import time
import os
import yagmail
import json
from dotenv import load_dotenv
from selenium.common.exceptions import WebDriverException, NoSuchElementException


def fetch_info():
    load_dotenv()

    try:
        IDS_json = os.getenv("IDS_JSON")
        if not IDS_json:
            raise ValueError("IDS_JSON is not set in the .env file.")
        IDS = json.loads(IDS_json)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON format for IDS_JSON in .env file") from e

    ROUTER_PASS = os.getenv("ROUTER_PASS")
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
    THRESHOLD_USAGE = int(os.getenv("THRESHOLD_USAGE", "11600"))
    EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")
    DRIVER_PATH = os.getenv("DRIVER_PATH", "/usr/local/bin/geckodriver")

    if not EMAIL_USER or not EMAIL_PASS:
        raise ValueError("EMAIL_USER and EMAIL_PASS must be set in the .env file")

    if not EMAIL_RECIPIENTS or EMAIL_RECIPIENTS == [""]:
        raise ValueError("EMAIL_RECIPIENTS must be set in the .env file")

    return (
        IDS,
        ROUTER_PASS,
        EMAIL_USER,
        EMAIL_PASS,
        EMAIL_RECIPIENTS,
        THRESHOLD_USAGE,
        DRIVER_PATH,
    )


IDS, ROUTER_PASS, EMAIL_USER, EMAIL_PASS, TO_EMAILS, THRESHOLD_USAGE, DRIVER_PATH = (
    fetch_info()
)
INDEX = 0


def main():
    global INDEX

    current_user = fetch_current_user()
    if current_user is None:
        print("Unable to fetch the current user. Exiting.")
        return

    usage = check_status(current_user)
    if usage is None:
        print("Unable to fetch usage. Exiting.")
        return

    if usage > 11000:
        INDEX = (INDEX + 1) % len(IDS)
        change_user(IDS[INDEX])
    else:
        scheduler(THRESHOLD_USAGE - usage)


def fetch_current_user():
    driver = get_driver()
    try:
        driver.get("http://192.168.0.1")
        driver.implicitly_wait(10)
        driver.find_element(By.ID, "pcPassword").send_keys(ROUTER_PASS)
        driver.find_element(By.ID, "loginBtn").click()
        driver.implicitly_wait(10)

        driver.switch_to.frame("frame1")
        driver.find_element(By.ID, "menu_network").click()
        driver.switch_to.default_content()
        driver.switch_to.frame("frame2")

        username_field = driver.find_element(By.ID, "username")
        for idx, ID in enumerate(IDS):
            if ID["username"] == username_field.get_attribute("value"):
                return ID
        print("No matching user found.")
        return None
    except WebDriverException as e:
        print(f"Error in fetching current user: {e}")
        send_email(
            "Change User Error", f"Error in fetching current user: {e}", TO_EMAILS
        )
        return None
    finally:
        driver.quit()


def get_driver():
    service = Service("/usr/local/bin/geckodriver")
    return webdriver.Firefox(service=service)


def change_user(user):
    driver = get_driver()
    try:
        driver.get("http://192.168.0.1")
        driver.implicitly_wait(10)
        driver.find_element(By.ID, "pcPassword").send_keys(ROUTER_PASS)
        driver.find_element(By.ID, "loginBtn").click()
        driver.implicitly_wait(10)

        driver.switch_to.frame("frame1")
        driver.find_element(By.ID, "menu_network").click()
        driver.switch_to.default_content()
        driver.switch_to.frame("frame2")

        username_field = driver.find_element(By.ID, "username")
        driver.execute_script("arguments[0].value = '';", username_field)
        username_field.send_keys(user["username"])

        password_field = driver.find_element(By.ID, "pwd")
        confirm_password_field = driver.find_element(By.ID, "pwd2")

        driver.execute_script("arguments[0].value = '';", password_field)
        password_field.send_keys(user["password"])

        driver.execute_script("arguments[0].value = '';", confirm_password_field)
        confirm_password_field.send_keys(user["password"])

        driver.find_element(By.ID, "saveBtn").click()
    except WebDriverException as e:
        print(f"Error in change_user: {e}")
        send_email(
            "Change User Error",
            f"Error changing user to {user['name']}: {e}",
            TO_EMAILS,
        )
    finally:
        driver.quit()


def check_status(user):
    driver = get_driver()
    try:
        driver.get("http://10.220.20.12/index.php/home/login")
        driver.find_element(By.ID, "username").send_keys(user["username"])
        driver.find_element(By.ID, "password").send_keys(user["password"])
        driver.find_element(By.XPATH, "//button[text()='Sign In']").click()
        driver.implicitly_wait(5)

        usage = int(
            driver.find_element(
                By.XPATH, "(//td[contains(normalize-space(text()), 'Minute')])[1]"
            ).text.split(" ")[0]
        )
        print(f"Usage for {user['name']}: {usage} minutes")
        return usage
    except (NoSuchElementException, ValueError, WebDriverException) as e:
        print(f"Error in check_status: {e}")
        send_email(
            "Check Status Error",
            f"Error checking status for {user['name']}: {e}",
            TO_EMAILS,
        )
        return None
    finally:
        driver.quit()


def send_email(subject, body, to_emails):
    try:
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
        yag.send(to=to_emails, subject=subject, contents=body)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")


def scheduler(minutes):
    schedule.every(minutes).minutes.do(lambda: main())
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
