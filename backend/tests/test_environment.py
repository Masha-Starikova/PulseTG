"""Страховка: окружение тестов не должно дотянуться до внешнего мира и dev-данных."""

import socket

import pytest
from pytest_socket import SocketConnectBlockedError

from backend.core.config import settings


@pytest.mark.filterwarnings("ignore:A test tried to use socket")
def test_outgoing_network_is_blocked() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(SocketConnectBlockedError):
            sock.connect(("1.1.1.1", 443))


def test_settings_point_to_isolated_test_resources() -> None:
    assert settings.database_url.endswith("_test")
    assert settings.openai_api_key == ""
    assert settings.telegram_api_hash == ""
