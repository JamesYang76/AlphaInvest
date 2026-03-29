"""
섹터·지역·자산군 ETF 벤치마크 — yfinance 기반 모멘텀(Chart 노드)용 유니버스.

운용/리서치에서 쓰는 대표 티커를 고정해 두고, 동일 스케일로 상대 강도를 비교한다.
"""

from typing import Final, List, Tuple

# (심볼, 표시용 그룹명) — 순서는 리포트 나열 순
SECTOR_MOMENTUM_BENCHMARKS: Final[List[Tuple[str, str]]] = [
    # 해외·신흥 (EM / 아시아)
    ("EWY", "한국"),
    ("FXI", "중국"),
    ("KWEB", "중국 인터넷"),
    ("EWJ", "일본"),
    ("EWT", "대만"),
    ("INDA", "인도"),
    ("VNM", "베트남"),
    ("VWO", "신흥국(VWO)"),
    ("IEMG", "신흥국(IEMG)"),
    # 미국 섹터 / 테크
    ("XLK", "미국 IT(XLK)"),
    ("VGT", "미국 IT(VGT)"),
    ("SOXX", "반도체(SOXX)"),
    ("SMH", "반도체(SMH)"),
    ("XLF", "금융"),
    ("XLV", "헬스케어"),
    ("XLE", "에너지"),
    ("XLC", "통신"),
    ("XLY", "경기소비재"),
    ("XLP", "필수소비재"),
    ("VHT", "헬스케어(VHT)"),
    ("XLI", "산업재"),
    ("XLU", "유틸리티"),
    ("BOTZ", "로봇·AI(BOTZ)"),
    ("ROBO", "로봇(ROBO)"),
    # 원자재
    ("GLD", "금"),
    ("SLV", "은"),
    ("USO", "원유"),
    ("UNG", "천연가스"),
    # 금리·크레딧
    ("TLT", "장기국채(20Y+)"),
    ("AGG", "종합 투자등급 채권"),
    ("HYG", "하이일드"),
    ("LQD", "투자등급 회사채"),
    ("VGSH", "단기 국채(1~3Y)"),
    ("IEF", "중기 국채(7~10Y)"),
]


def sector_momentum_symbols() -> List[str]:
    """벤치마크 심볼만 순서 유지해 반환 (중복 없음)."""
    seen: set[str] = set()
    out: List[str] = []
    for sym, _ in SECTOR_MOMENTUM_BENCHMARKS:
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def label_for_symbol(symbol: str) -> str:
    """표시용 짧은 라벨."""
    for sym, lab in SECTOR_MOMENTUM_BENCHMARKS:
        if sym == symbol:
            return lab
    return symbol
