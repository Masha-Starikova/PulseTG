import logging


def setup_logging(debug: bool = False) -> None:
    """Настройка логирования с единым форматом для всех сервисов."""

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
