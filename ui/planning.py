from typing import Any, Callable

import streamlit as st


StatusRunner = Callable[..., Any]


def render_idea_tab(
    app: Any,
    *,
    ensure_api_key: Callable[[], bool],
    run_with_status: StatusRunner,
) -> None:
    planner = app.planner

    st.subheader("아이디어/제목")
    st.caption("프로젝트 통합 설정 안에서 쓰는 보조 도구입니다.")
    st.markdown("플랫폼, 키워드, 원하는 톤을 바탕으로 소설 아이디어와 제목 후보를 생성합니다.")

    idea_platform = st.text_input(
        "플랫폼",
        value="문피아, 카카오페이지, 네이버시리즈",
        key="idea_platform",
    )
    idea_keywords = st.text_input(
        "관심 키워드",
        value="회귀, 아카데미, 성장, 코미디",
        key="idea_keywords",
    )
    idea_tone = st.text_area(
        "원하는 톤",
        value="가볍고 팝한",
        height=100,
        placeholder="예: 건조하고 냉소적인 다크 판타지, 유쾌한 성장물",
        key="idea_tone",
    )

    if st.button("아이디어/제목 생성", type="primary", width="stretch", key="btn_idea_gen"):
        if ensure_api_key():
            idea_result = run_with_status(
                lambda: planner.suggest_ideas(
                    platform_name=idea_platform,
                    user_keywords=idea_keywords,
                    tone=idea_tone,
                ),
                "아이디어를 생성하는 중입니다...",
                llm_error_prefix="아이디어 생성 실패",
                error_prefix="아이디어 생성 중 오류가 발생했습니다",
            )
            if idea_result is not None:
                st.session_state["idea_result"] = idea_result

    if st.session_state.get("idea_result"):
        st.text_area(
            "추천 결과",
            value=st.session_state["idea_result"],
            height=360,
            key="idea_result_view",
        )


def render_plot_tab(
    app: Any,
    *,
    ensure_api_key: Callable[[], bool],
    run_with_status: StatusRunner,
) -> None:
    generator = app.generator
    planner = app.planner

    st.subheader("대형 플롯")
    st.caption("프로젝트 통합 설정 안에서 쓰는 보조 도구입니다.")
    st.markdown("300화 안팎 장편 기준으로 거시 플롯과 30화 단위 대형 사건 구성을 생성합니다.")

    left_col, right_col = st.columns(2)
    with left_col:
        plot_platform = st.text_input("플랫폼", value="네이버시리즈", key="plot_platform")
        plot_title = st.text_input("작품 제목", value="망한 아카데미에서 살아남는 법", key="plot_title")
        phase1_focus = st.text_area(
            "1~100화 중점",
            value="입문자 흡입력과 주인공 성장",
            height=90,
            key="plot_phase1",
        )
    with right_col:
        phase2_focus = st.text_area(
            "101~200화 중점",
            value="중형 갈등 심화와 세계 확장",
            height=90,
            key="plot_phase2",
        )
        phase3_focus = st.text_area(
            "201~300화 중점",
            value="세계관 비밀 공개와 대단원",
            height=90,
            key="plot_phase3",
        )

    if st.button("대형 플롯 생성", type="primary", width="stretch", key="btn_plot_gen"):
        if not ensure_api_key():
            return
        if not plot_title.strip():
            st.warning("제목을 입력해 주세요.")
            return

        plot_result = run_with_status(
            lambda: planner.build_macro_plot(
                platform_name=plot_platform,
                title=plot_title,
                phase1_focus=phase1_focus,
                phase2_focus=phase2_focus,
                phase3_focus=phase3_focus,
                total_episodes=300,
            ),
            "대형 플롯을 설계하는 중입니다...",
            llm_error_prefix="플롯 생성 실패",
            error_prefix="플롯 생성 중 오류가 발생했습니다",
        )
        if plot_result is not None:
            st.session_state["plot_result"] = plot_result

    if st.session_state.get("plot_result"):
        st.text_area("플롯 결과", value=st.session_state["plot_result"], height=360, key="plot_result_view")
        save_col, load_col = st.columns(2)
        with save_col:
            if st.button("플롯을 프로젝트 설정에 저장", width="stretch", key="btn_plot_save"):
                generator.ctx.save_plot_outline(st.session_state["plot_result"])
                st.success("플롯을 저장했습니다. 회차 생성 탭에서 반영할 수 있습니다.")
        with load_col:
            if st.button("저장된 플롯 불러오기", width="stretch", key="btn_plot_load"):
                saved_plot = generator.ctx.get_plot_outline()
                if saved_plot:
                    st.session_state["plot_result"] = saved_plot
                    st.success("저장된 플롯을 불러왔습니다.")
                else:
                    st.info("저장된 플롯이 없습니다.")
