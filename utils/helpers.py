from utils.logger import get_logger

logger = get_logger("utils.helpers")


def print_welcome_message(app_name: str):
    """
    앱 이름을 받아 시스템 초기화 메시지를 출력.
    """
    logger.info(f"{app_name} 시스템 파이프라인 준비 중...")
    logger.info("데이터베이스 연결 및 리소스 로드를 대기합니다.")
