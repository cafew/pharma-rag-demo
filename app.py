from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pdf_utils import get_pdf_page_count, render_annotated_page
from rag import search_manual


BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "data" / "manual.pdf"


def initialize_session_state() -> None:
    """Set defaults for interactive UI state."""
    defaults = {
        "search_results": [],
        "selected_page": 1,
        "selected_text": "",
        "selected_score": None,
        "search_executed": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def run_search(question: str) -> None:
    """Search the vector store and update the selected result."""
    results = search_manual(question, top_k=5)
    st.session_state.search_results = results
    st.session_state.search_executed = True

    if results:
        first_result = results[0]
        st.session_state.selected_page = first_result["page_number"]
        st.session_state.selected_text = first_result["text"]
        st.session_state.selected_score = first_result["score"]
    else:
        st.session_state.selected_text = ""
        st.session_state.selected_score = None


def select_result(result: dict) -> None:
    """Update the page viewer when a result is selected."""
    st.session_state.selected_page = result["page_number"]
    st.session_state.selected_text = result["text"]
    st.session_state.selected_score = result["score"]


def main() -> None:
    """Launch the Streamlit demo."""
    load_dotenv()
    st.set_page_config(page_title="医薬品コールセンター RAG デモ", layout="wide")
    initialize_session_state()

    st.title("医薬品コールセンター RAG デモ")

    if not PDF_PATH.exists():
        st.error("data/manual.pdf が見つかりません。PDF を配置してから再実行してください。")
        st.stop()

    total_pages = get_pdf_page_count(PDF_PATH)

    left_col, right_col = st.columns([1.0, 1.2], gap="large")

    with left_col:
        st.subheader("質問検索")
        question = st.text_input(
            "薬局からの質問を入力してください",
            placeholder="例：腎機能低下患者への投与量は？",
        )

        if st.button("検索", type="primary", use_container_width=True):
            if not question.strip():
                st.warning("質問を入力してください。")
            else:
                with st.spinner("関連箇所を検索しています..."):
                    try:
                        run_search(question)
                    except Exception as exc:
                        st.session_state.search_results = []
                        st.error(f"検索に失敗しました: {exc}")

        st.subheader("検索結果")
        if st.session_state.search_results:
            for index, result in enumerate(st.session_state.search_results, start=1):
                similarity = max(0.0, min(1.0, float(result["score"])))
                similarity_percent = similarity * 100
                with st.container(border=True):
                    st.markdown(f"**{index}. ページ {result['page_number']}**")
                    st.caption(f"類似度: {similarity_percent:.1f}%")
                    st.progress(int(round(similarity_percent)))
                    st.write(result["snippet"])

                    if st.button(
                        "この結果を表示",
                        key=f"select_result_{index}",
                        use_container_width=True,
                    ):
                        select_result(result)
                        st.rerun()
        elif st.session_state.search_executed:
            st.info("該当する結果が見つかりませんでした。")
        else:
            st.caption("質問を入力して検索すると、関連チャンクがここに表示されます。")

    with right_col:
        st.subheader("PDF ビュー")
        nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 2])

        if nav_col1.button("前のページ", disabled=st.session_state.selected_page <= 1):
            st.session_state.selected_page -= 1
            st.rerun()

        if nav_col2.button("次のページ", disabled=st.session_state.selected_page >= total_pages):
            st.session_state.selected_page += 1
            st.rerun()

        nav_col3.caption(f"{st.session_state.selected_page} / {total_pages} ページ")

        with st.spinner("PDF ページを描画しています..."):
            try:
                image, matched_terms, match_count = render_annotated_page(
                    pdf_path=PDF_PATH,
                    page_number=st.session_state.selected_page,
                    question=question,
                    selected_text=st.session_state.selected_text,
                )
            except Exception as exc:
                st.error(f"PDF の描画に失敗しました: {exc}")
                st.stop()

        st.image(image, use_container_width=True)

        if matched_terms:
            st.caption(f"ハイライト候補: {' / '.join(matched_terms[:4])}")
            st.caption(f"検出数: {match_count}")
        else:
            st.caption("現在のページではハイライト対象が見つかりませんでした。")


if __name__ == "__main__":
    main()
