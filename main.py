from utils.logger import get_logger
from utils.helpers import print_welcome_message

logger = get_logger("main")

def main():
    logger.info("🚀 AlphaInvest 에이전트 실행을 시작합니다...")
    
    # 1. 분리된 utils 함수 호출
    print_welcome_message("AlphaInvest")
    
    logger.warning("현재는 초기 구조만 잡힌 상태이며, LangGraph 워크플로우를 구현하여 이곳에 연결할 예정입니다.")

if __name__ == "__main__":
    main()
