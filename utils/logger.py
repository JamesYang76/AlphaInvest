import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    AlphaInvest 프로젝트 공통 로거를 반환하는 함수입니다.
    """
    logger = logging.getLogger(name)
    
    # 중복 핸들러 생성 방지
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # 콘솔 핸들러 설정
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 포멧터: [시간] [로그레벨] [모듈명] 메시지 형식
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
    return logger
