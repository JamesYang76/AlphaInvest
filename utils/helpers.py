from utils.logger import get_logger

logger = get_logger("utils.helpers")


def export_graph_visualization(app) -> None:
    """마크다운(.md) 및 이미지(.png) 포맷 두 가지로 다이어그램을 산출합니다."""

    # 1. Markdown(.md) 추출
    mermaid_text = app.get_graph().draw_mermaid()
    mermaid_text = mermaid_text.replace("<p>", "").replace("</p>", "")

    import re

    mermaid_text = re.sub(r"^---\nconfig:.*?\n---\n", "", mermaid_text, flags=re.DOTALL)

    md_content = f"## 📊 AlphaInvest Architecture Flow\n\n```mermaid\n{mermaid_text}\n```\n"
    with open("graph_flow.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    # 2. PNG 이미지 렌더링 (그림 자체를 저장하여 에디터 한계를 원천 회피)
    try:
        png_data = app.get_graph().draw_mermaid_png()
        with open("graph_flow.png", "wb") as f:
            f.write(png_data)
        logger.info("아키텍처 다이어그램이 'graph_flow.md' 및 'graph_flow.png'에 모두 산출되었습니다.")
    except Exception as e:
        logger.warning(f"PNG 이미지 산출 중 에러 발생 (인터넷 API 연결 필요): {e}")
