import pytest
from unittest.mock import patch, MagicMock
import project


@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv(
        "IDS_JSON",
        '[{"username": "testuser", "password": "testpass", "name": "Test User"}]',
    )
    monkeypatch.setenv("ROUTER_PASS", "routerpass")
    monkeypatch.setenv("EMAIL_USER", "test@example.com")
    monkeypatch.setenv("EMAIL_PASS", "emailpass")


@pytest.fixture
def mock_driver():
    with patch("project.webdriver.Firefox") as MockWebDriver:
        mock_driver = MagicMock()
        MockWebDriver.return_value = mock_driver
        yield mock_driver


def test_get_driver(mock_driver):
    driver = project.get_driver()
    assert driver == mock_driver


def test_change_user(mock_env_vars, mock_driver):
    project.INDEX = 0
    project.change_user(project.IDS[0])
    assert mock_driver.get.called
    assert mock_driver.find_element.called


def test_send_email(mock_env_vars):
    with patch("project.yagmail.SMTP") as MockSMTP:
        mock_smtp = MockSMTP.return_value
        project.send_email("Test Subject", "Test Body", ["test@example.com"])
        assert mock_smtp.send.called
