import logging
import os  # 추가
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        # 환경 변수에서 로그 레벨을 읽어옵니다. (기본값: INFO)
        # 만약 LOG_LEVEL=WARNING 이라고 설정하면 INFO 로그는 안 나오게 됩니다.
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        logger.setLevel(log_level)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)  # 핸들러 레벨도 맞춰줍니다.

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
