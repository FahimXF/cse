from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import schedule
import time
import os

IDS = [
    {"name": "Fahim", "username": "shahriarfahim", "password": "XF12345"},
    {"name": "Asif", "username": "asifulislam53", "password": "asifulislam1234"},
    {"name": "Jubair", "username": "jubairmasud", "password": "jubair133"},
    {"name": "Tahmid", "username": "tahmidhassan22", "password": "Muhsan919"},
]
ROUTER_PASS = os.getenv("ROUTER_PASS", "a53b26c33d28")
index = 0


def get_driver():
    service = Service("/usr/local/bin/geckodriver")
    return webdriver.Firefox(service=service)


def change_user(driver, user):
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
        driver.execute_script(
            "arguments[0].value = '';", driver.find_element(By.ID, "username")
        )
        driver.find_element(By.ID, "username").send_keys(user["username"])
        driver.find_element(By.ID, "pwd").send_keys(user["password"])
        driver.find_element(By.ID, "pwd2").send_keys(user["password"])
        driver.find_element(By.ID, "saveBtn").click()
    except Exception as e:
        print(f"Error in change_user: {e}")
    finally:
        driver.quit()


def check_status():
    global index
    driver = get_driver()
    try:
        driver.get("http://10.220.20.12/index.php/home/login")
        driver.find_element(By.ID, "username").send_keys(IDS[index]["username"])
        driver.find_element(By.ID, "password").send_keys(IDS[index]["password"])
        driver.find_element(By.XPATH, "//button[text()='Sign In']").click()
        driver.implicitly_wait(2)

        usage = int(
            driver.find_element(
                By.XPATH, "(//td[contains(normalize-space(text()), 'Minute')])[1]"
            ).text.split(" ")[0]
        )
        print(f"Usage for {IDS[index]['name']}: {usage} minutes")
        if usage > 11600:
            index = (index + 1) % len(IDS)
            change_user(driver, IDS[index])
        else:
            scheduler(11600 - usage)
    except Exception as e:
        print(f"Error in check_status: {e}")
    finally:
        driver.quit()


def scheduler(minutes):
    schedule.every(minutes).minutes.do(check_status)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    check_status()
