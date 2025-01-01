from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import schedule
import time


service = Service("/usr/local/bin/geckodriver")
driver = webdriver.Firefox(service=service)

global ids
ids = [
    {"name": "Fahim", "username": "shahriarfahim", "password": "XF12345"},
    {"name": "Asif", "username": "asifulislam53", "password": "asifulislam1234"},
    {"name": "jubair", "username": "jubairmasud", "password": "jubair133"},
    {"name": "tahmid", "username": "tahmidhassan22", "password": "Muhsan919"},
]
global router_pass
router_pass = "a53b26c33d28"

global i
i = 0


def change_user():
    driver.get("http://192.168.0.1")
    driver.implicitly_wait(10)

    driver.find_element(By.ID, "pcPassword").send_keys(router_pass)
    driver.find_element(By.ID, "loginBtn").click()
    driver.implicitly_wait(10)

    driver.switch_to.frame("frame1")
    driver.find_element(By.ID, "menu_network").click()
    driver.switch_to.default_content()

    driver.switch_to.frame("frame2")

    username_field = driver.find_element(By.ID, "username")
    driver.execute_script("arguments[0].value = '';", username_field)
    username_field.send_keys(ids[i]["username"])

    password_field = driver.find_element(By.ID, "pwd")
    confirm_password_field = driver.find_element(By.ID, "pwd2")

    driver.execute_script("arguments[0].value = '';", password_field)
    password_field.send_keys(ids[i]["password"])

    driver.execute_script("arguments[0].value = '';", confirm_password_field)
    confirm_password_field.send_keys(ids[i]["password"])

    # Attempt to save and handle alerts if necessary
    driver.find_element(By.ID, "saveBtn").click()

    driver.quit()

    return


def check_status():
    global i
    driver.get("http://10.220.20.12/index.php/home/login")
    driver.find_element(By.ID, "username").send_keys(ids[i]["username"])
    driver.find_element(By.ID, "password").send_keys(ids[i]["password"])
    driver.find_element(By.XPATH, "//button[text()='Sign In']").click()
    driver.implicitly_wait(2)
    usage = int(
        driver.find_element(
            By.XPATH, "(//td[contains(normalize-space(text()), 'Minute')])[1]"
        ).text.split(" ")[0]
    )

    print(usage)
    if usage > 11600:
        i = (i + 1) % 4
        change_user()
        return

    scheduler(11600 - usage)
    driver.quit()


def scheduler(minutes):
    schedule.every(minutes).minutes.do(check_status)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    # change_user()
    check_status()
