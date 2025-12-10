import streamlit as st
import calendar
import os
import pandas as pd
import sentinel_core as core   # ← 네가 업로드한 메인 알고리즘 파일 이름

# ===============================================================
# Streamlit Page Layout / Theme
# ===============================================================

st.set_page_config(
    page_title="Sentinel AIP-lite · 2소대 공정작전 근무표",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS (Palantir AIP 스타일 느낌)
st.markdown(
    """
    <style>
        /* Layout Tweaks */
        .block-container {
            padding-top: 1rem;
            padding-left: 2.5rem;
            padding-right: 2.5rem;
        }
        
        /* Title style */
        .title-box {
            padding: 18px 22px;
            border-radius: 14px;
            background: linear-gradient(90deg, #0f172a, #020617);
            color: white;
            margin-bottom: 16px;
        }
        .subtitle {
            color: #cbd5e1;
            font-size: 0.9rem;
            margin-top: -6px;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #0f172a !important;
        }
        section[data-testid="stSidebar"] * {
            color: #cbd5e1 !important;
        }

        .stTabs [role="tab"] {
            font-size: 16px;
            padding: 10px 20px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ===============================================================
# Header
# ===============================================================

st.markdown(
    """
    <div class="title-box">
        <h2 style="margin-bottom:6px;">🛡️ Sentinel AIP-lite – 2소대 경계작전 공정표</h2>
        <div class="subtitle">Palantir AIP 스타일로 2소대 경계작전 공정표를 설계, 배치, 모니터링합니다.</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ===============================================================
# YEAR / MONTH 입력 — sidebar에서 제거하고 메인 영역으로 이동
# ===============================================================

st.markdown("### ⚙️ 근무표 설정")

col_year, col_month = st.columns(2)

with col_year:
    year = st.number_input(
        "연도 (YEAR)",
        min_value=2023,
        max_value=2030,
        value=2025,
        step=1
    )

with col_month:
    month = st.number_input(
        "월 (MONTH)",
        min_value=1,
        max_value=12,
        value=12,
        step=1
    )

# ===============================================================
# Tabs
# ===============================================================

tab_dashboard, tab_generate, tab_stats, tab_newcomer, tab_manual = st.tabs(
    ["📊 대시보드", "📅 근무표 생성", "👥 개별 통계", "🧑‍✈️ 신병 투입 / 팀 재배치", "✏️ 근무표 수동 수정"]
)

# ===============================================================
# 1) Dashboard
# ===============================================================

with tab_dashboard:
    st.subheader("📊 Sentinel Guard Planner Overview")

    # 기본 요약 (아직 근무표 생성 전)
    if "latest_schedule" not in st.session_state:
        st.info("아직 생성된 근무표가 없습니다. 왼쪽 탭 [📅 근무표 생성] 으로 이동하여 먼저 생성하세요.")
    else:
        st.success("최근 생성된 근무표를 불러왔습니다.")

    st.markdown("### 요약 뷰")

    if "latest_stats_df" not in st.session_state:
        st.info("공정표가 없어요. 왼쪽 탭에서 생성해주세요.")
    else:
        st.dataframe(st.session_state["latest_stats_df"])


# ===============================================================
# Helper: Run Scheduler
# ===============================================================

def run_scheduler(year: int, month: int):
    """core.py와 연결하여 근무표 생성 후 통계 반환"""

    # core.py 전역 변수 업데이트
    core.YEAR = year
    core.MONTH = month
    core.DAYS = calendar.monthrange(year, month)[1]

    core.FILE_VAC = f"{month:02d}월 휴가.xlsx"
    core.OUT_PATH = f"{year}년_{month:02d}월_공정표_경작서.xlsx"

    # 근무표 생성
    core.main()

    # 멤버 & 스케줄 로드
    members = core.load_members(core.FILE_SQUADS)
    schedule = core.load_schedule_from_excel(core.OUT_PATH, members, core.DAYS)
    fairness = core.compute_excel_style_fairness(
        schedule, members, year, month, core.DAYS
    )

    # 개별 통계 계산
    def parse_shift(tag: str):
        t = str(tag or "").strip()
        if t.startswith("주간"):
            return "D"
        if t.startswith("야간"):
            return "N"
        if t == "예비":
            return "R"
        if t == "휴가":
            return "V"
        return ""

    rows = []
    for m in members:
        d_cnt = n_cnt = r_cnt = v_cnt = 0
        for d in range(1, core.DAYS + 1):
            s = parse_shift(schedule[d].get(m, ""))
            if s == "D": d_cnt += 1
            elif s == "N": n_cnt += 1
            elif s == "R": r_cnt += 1
            elif s == "V": v_cnt += 1

        rows.append(
            {
                "이름": m,
                "주간": d_cnt,
                "야간": n_cnt,
                "예비": r_cnt,
                "휴가": v_cnt,
                "공정성 점수": fairness.get(m, 0)
            }
        )

    stats_df = pd.DataFrame(rows)
    return core.OUT_PATH, stats_df


# ===============================================================
# 2) 근무표 생성 탭
# ===============================================================

with tab_generate:
    st.subheader("📅 근무표 자동 생성 (CP-SAT Solver)")

    st.markdown(
        """
        - OR-Tools CP-SAT + ML 기반 힌트를 사용하여 한 달치 근무표를 자동 생성합니다.  
        - 아래 [근무표 생성하기] 버튼을 누르면 알고리즘이 실행됩니다.
        """
    )

    if st.button("🚀 이 설정으로 근무표 생성하기", type="primary"):
        with st.spinner("CP-SAT Solver 실행 중입니다... (약간의 시간이 걸릴 수 있어요)"):
            try:
                out_path, stats_df = run_scheduler(int(year), int(month))
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
            else:
                st.success(f"✅ 근무표 생성 완료! 결과 파일: {out_path}")

                # 파일 다운로드
                if os.path.exists(out_path):
                    with open(out_path, "rb") as f:
                        st.download_button(
                            label="📥 생성된 엑셀 파일 다운로드",
                            data=f,
                            file_name=os.path.basename(out_path),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                # 요약 통계 표시
                st.markdown("### 📈 근무 통계 요약")
                st.dataframe(stats_df)

                # 공정성 점수 바 차트
                chart_df = stats_df[["이름", "공정성 점수"]].set_index("이름")
                st.bar_chart(chart_df)

                # 세션 저장
                st.session_state["latest_stats_df"] = stats_df
                st.session_state["latest_schedule"] = out_path


# ===============================================================
# 3) 개별 통계 탭
# ===============================================================

with tab_stats:
    st.subheader("👥 개별 병사 근무 통계")

    stats_df = st.session_state.get("latest_stats_df", None)

    if stats_df is None:
        st.info("먼저 [📅 근무표 생성] 탭에서 근무표를 만들어주세요.")
    else:
        col1, col2 = st.columns([1, 2])
        selected = col1.selectbox("병사 선택", stats_df["이름"].tolist())

        row = stats_df[stats_df["이름"] == selected].iloc[0]

        with col1:
            st.metric("공정성 점수", f"{row['공정성 점수']:.0f}")
            st.metric("주간", row["주간"])
            st.metric("야간", row["야간"])
            st.metric("예비", row["예비"])
            st.metric("휴가", row["휴가"])

        with col2:
            pie_df = pd.DataFrame(
                {"종류": ["주간", "야간", "예비", "휴가"],
                 "일수": [row["주간"], row["야간"], row["예비"], row["휴가"]]}
            )
            st.bar_chart(pie_df.set_index("종류"))


# ===============================================================
# 4) 신병 투입 / 팀 재배치 (Mock)
# ===============================================================

with tab_newcomer:
    st.subheader("🧑‍✈️ 신병 투입 / 팀 재배치 (Prototype)")

    st.info("이 기능은 다음 버전에서 실제 알고리즘이 추가됩니다. 지금은 UI 프로토타입 상태입니다.")

    with st.form("newcomer_form"):
        new_name = st.text_input("신병 이름")
        role = st.selectbox("역할", ["사수", "부사수"])
        start_day = st.number_input("투입 시작일", 1, 31, 1)
        end_day = st.number_input("투입 종료일", 1, 31, 7)
        submitted = st.form_submit_button("🧮 재배치 시뮬레이션")

    if submitted:
        st.success(
            f"'{new_name}' ({role}) 을/를 {start_day}일 ~ {end_day}일 구간에 넣었을 때 "
            "공정성 변화와 충돌 여부를 분석하는 기능이 다음 버전에서 추가될 예정입니다."
        )


# ===============================================================
# 5) 근무표 수동 수정 (Prototype)
# ===============================================================

with tab_manual:
    st.subheader("✏️ 근무표 수동 수정 (Prototype)")

    uploaded = st.file_uploader("수정하고 싶은 근무표(.xlsx) 업로드", type=["xlsx"])

    if uploaded:
        st.info("이 탭은 향후 '셀 기반 수정 + 규칙 위반 자동 체크' 기능으로 확장됩니다.")
        df = pd.read_excel(uploaded)
        st.dataframe(df)
