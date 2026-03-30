"""
섹터·지역·자산군 ETF 벤치마크 — yfinance 기반 모멘텀(Chart 노드)용 유니버스.

운용/리서치에서 쓰는 대표 티커를 고정해 두고, 동일 스케일로 상대 강도를 비교한다.
"""

from typing import Final, List, Tuple

TREEMAP_GROUP_ORDER: Final[List[str]] = [
    "세계 주식",
    "미국 주식(섹터별)",
    "미국 주식(스타일별)",
    "미국 채권",
    "원자재",
]

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
    ("ACWI", "글로벌(ACWI)"),
    ("IEMG", "신흥국(IEMG)"),
    ("SPDW", "선진국 ex-US(SPDW)"),
    ("VEA", "선진국(VEA)"),
    ("IEFA", "EAFE(IEFA)"),
    # 유럽
    ("VGK", "유럽(통합)"),
    ("EZU", "유로존"),
    ("EWU", "영국"),
    ("EWG", "독일"),
    ("EWQ", "프랑스"),
    ("EWL", "스위스"),
    ("EWP", "스페인"),
    ("EWN", "네덜란드"),
    ("FEZ", "유로스톡스50"),
    # 북중미·라틴 (미국 국가 지수)
    ("EWC", "캐나다"),
    ("EWW", "멕시코"),
    ("EWZ", "브라질"),
    ("ILF", "라틴아메리카"),
    # 오세아니아·중동 등
    ("EWA", "호주"),
    ("EIS", "이스라엘"),
    # 미국 섹터 / 테크
    ("VTI", "미국 전체(VTI)"),
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
    # 미국 팩터·스타일 (Portfolio & Reports 벤치마크)
    ("IUSV", "미국 가치(IUSV)"),
    ("IUSG", "미국 성장(IUSG)"),
    ("QUAL", "퀄리티(QUAL)"),
    ("USMV", "저변동(USMV)"),
    ("VYM", "고배당(VYM)"),
    ("MTUM", "모멘텀(MTUM)"),
    ("DGRO", "배당성장(DGRO)"),
    ("RSP", "동일가중 S&P(RSP)"),
    # 디지털 자산 (미국 상장 현물 ETF)
    ("IBIT", "비트코인(IBIT)"),
    ("ETHA", "이더리움(ETHA)"),
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


def treemap_group_for_symbol(symbol: str) -> str:
    world_equities = {
        "EWY", "FXI", "KWEB", "EWJ", "EWT", "INDA", "VNM", "VWO", "ACWI", "IEMG",
        "SPDW", "VEA", "IEFA", "VGK", "EZU", "EWU", "EWG", "EWQ", "EWL", "EWP",
        "EWN", "FEZ", "EWC", "EWW", "EWZ", "ILF", "EWA", "EIS",
    }
    us_sectors = {
        "XLK", "VGT", "SOXX", "SMH", "XLF", "XLV", "XLE", "XLC", "XLY", "XLP", "VHT", "XLI", "XLU",
    }
    us_styles = {
        "VTI", "IUSV", "IUSG", "QUAL", "USMV", "VYM", "MTUM", "DGRO", "RSP",
    }
    us_bonds = {"TLT", "AGG", "HYG", "LQD", "VGSH", "IEF"}
    commodities = {"GLD", "SLV", "USO", "UNG", "IBIT", "ETHA"}

    if symbol in world_equities:
        return "세계 주식"
    if symbol in us_sectors:
        return "미국 주식(섹터별)"
    if symbol in us_styles:
        return "미국 주식(스타일별)"
    if symbol in us_bonds:
        return "미국 채권"
    if symbol in commodities:
        return "원자재"
    return ""
