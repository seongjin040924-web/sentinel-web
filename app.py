# app.py  (HuggingFace Spaces / Streamlit 전용)

import os
import io
import calendar
from datetime import datetime

import pandas as pd
import streamlit as st

import core  # 같은 폴더에 core.py 있어야 함


# =========================
# 0. 공통 유틸
# =========================
def set_year_month(year: int, month: int):
    """core 모듈의 YEAR, MONTH, DAYS, OUT_PATH 동적으로 변경."""
    core.YEAR = year
    core.MONTH = month
    core.DAYS = calendar.monthrange(year, month)[1]
    core.OUT_PATH = f"{year}년_{month:02d}월_공정표_경작서.xlsx"


def schedule_to_df(schedule: dict, members: list, days: int) -> pd.DataFrame:
    rows = []
    for m in members:
        row = {"이름": m}
        for d in range(1, days + 1):
            row[str(d)] = schedule[d].get(m, "")
        rows.append(row)
    return pd.DataFrame(rows)


def df_to_schedule(df: pd.DataFrame, days: int) -> dict:
    sched = {d: {} for d in range(1, days + 1)}
    for _, row in df.iterrows():
        name = str(row["이름"])
        for d in range(1, days + 1):
            tag = row.get(str(d), "")
            sched[d][name] = "" if pd.isna(tag) else str(tag)
    return sched


def compute_stats(schedule: dict, members: list, year: int, month: int, days: int) -> pd.DataFrame:
    # core.compute_excel_style_fairness 사용
    fair_map = core.compute_excel_style_fairness(schedule, members, year, month, days)
    data = []
    for m in members:
        day_cnt = 0
        night_cnt = 0
        reserve_cnt = 0
        vac_cnt = 0
        for d in range(1, days + 1):
            tag = str(schedule[d].get(m, "")).strip()
            if tag.startswith("주간"):
                day_cnt += 1
            elif tag.startswith("야간"):
                night_cnt += 1
            elif tag == "예비":
                reserve_cnt += 1
            elif tag == "휴가":
                vac_cnt += 1
        data.append(
            {
                "이름": m,
                "주간": day_cnt,
                "야간": night_cnt,
                "예비": reserve_cnt,
                "휴가": vac_cnt,
                "공정성 점수": fair_map.get(m, 0.0),
            }
        )
    return pd.DataFrame(data)


def download_excel_from_path(path: str, label: str):
    if not os.path.exists(path):
        st.warning("엑셀 파일이 아직 생성되지 않았습니다.")
        return
    with open(path, "rb") as f:
        data = f.read()
    st.download_button(
        label=label,
        data=data,
        file_name=os.path.basename(path),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# =========================
# 1. Palantir AIP 스타일 테마
# =========================
def inject_palantir_style():
    st.set_page_config(
        page_title="Sentinel AIP Web",
        layout="wide",
        page_icon="🛡️",
    )

    st.markdown(
        """
        <style>
        /* 전체 배경 */
        .stApp {
            background-color: #050710;
            color: #e5e7eb;
            font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        }
        /* 사이드바 */
        section[data-testid="stSidebar"] {
            background-color: #080b18;
            border-right: 1px solid #1f2937;
        }
        /* 카드 스타일 */
        .aip-card {
            border-radius: 12px;
            padding: 14px 18px;
            background: radial-gradient(circle at top left, #111827, #020617);
            border: 1px solid #1f2937;
        }
        .aip-card h3 {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #9ca3af;
            margin-bottom: 6px;
        }
        .aip-card .value {
            font-size: 1.4rem;
            font-weight: 600;
            color: #e5e7eb;
        }
        .aip-pill {
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 999px;
            background: #111827;
            border: 1px solid #1f2937;
            font-size: 0.7rem;
            color: #9ca3af;
        }
        .aip-accent {
            color: #38bdf8;
        }
        .aip-badge-ok {
            background: rgba(22, 163, 74, 0.1);
            border-color: #16a34a;
            color: #bbf7d0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# 2. 스트림릿 페이지 구성
# =========================
def main():
    inject_palantir_style()

    st.sidebar.title("🛡️ Sentinel AIP Web")
    st.sidebar.caption("2소대 공정표 · Palantir AIP 스타일 대시보드")

    # ---- 파일 업로드 (필수 엑셀 4종) ----
    st.sidebar.subheader("📂 입력 파일 업로드")
    squads_file = st.sidebar.file_uploader("분대편성표.xlsx", type=["xlsx"])
    vac_file = st.sidebar.file_uploader("12월 휴가.xlsx", type=["xlsx"])
    guns_file = st.sidebar.file_uploader("총기.xlsx", type=["xlsx"])
    rank_file = st.sidebar.file_uploader("짬표.xlsx", type=["xlsx"])

    # 업로드된 파일을 core에서 기대하는 이름으로 저장
    if squads_file:
        with open(core.FILE_SQUADS, "wb") as f:
            f.write(squads_file.read())
    if vac_file:
        with open(core.FILE_VAC, "wb") as f:
            f.write(vac_file.read())
    if guns_file:
        with open(core.FILE_GUNS, "wb") as f:
            f.write(guns_file.read())
    if rank_file:
        with open(core.FILE_RANK, "wb") as f:
            f.write(rank_file.read())

    st.sidebar.markdown("---")

    # ---- 년/월 설정 ----
    today = datetime.today()
    default_year = core.YEAR if hasattr(core, "YEAR") else today.year
    default_month = core.MONTH if hasattr(core, "MONTH") else today.month

    year = st.sidebar.number_input("년도 (YEAR)", min_value=2024, max_value=2030, value=default_year, step=1)
    month = st.sidebar.number_input("월 (MONTH)", min_value=1, max_value=12, value=default_month, step=1)

    set_year_month(int(year), int(month))

    st.sidebar.markdown(
        f"""
        <div class="aip-card" style="margin-top: 8px;">
          <h3>현재 설정</h3>
          <div class="value">{core.YEAR}년 {core.MONTH}월</div>
          <div style="margin-top:4px;font-size:0.7rem;color:#9ca3af;">
            DAYS = {core.DAYS}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.title("🛡️ Sentinel AIP Web")
    st.caption("야간·주간·예비 공정표 + Palantir AIP 스타일 분석 대시보드")

    # 상단 KPI 카드
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.markdown(
            f"""
            <div class="aip-card">
              <h3>MONTH</h3>
              <div class="value">{core.YEAR}.{core.MONTH:02d}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f"""
            <div class="aip-card">
              <h3>DAYS</h3>
              <div class="value">{core.DAYS}일</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_c:
        members_preview = []
        if os.path.exists(core.FILE_SQUADS):
            try:
                members_preview = core.load_members(core.FILE_SQUADS)
            except Exception:
                members_preview = []
        m_cnt = len(members_preview)
        st.markdown(
            f"""
            <div class="aip-card">
              <h3>총 인원</h3>
              <div class="value">{m_cnt if m_cnt > 0 else '-'} 명</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_d:
        st.markdown(
            """
            <div class="aip-card">
              <h3>STATUS</h3>
              <div class="value aip-accent">Online</div>
              <div class="aip-pill aip-badge-ok" style="margin-top:6px;">
                Solver Ready
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # 메인 탭
    tab_gen, tab_newcomer, tab_edit = st.tabs(
        ["📅 공정표 생성", "🪖 신병 투입 / 재배치", "✏️ 수동 수정 & 엑셀 다운로드"]
    )

    # =========================
    # 📅 1) 공정표 생성 탭
    # =========================
    with tab_gen:
        st.subheader("📅 공정표 생성 (월 전체)")

        if not (os.path.exists(core.FILE_SQUADS) and os.path.exists(core.FILE_VAC)
                and os.path.exists(core.FILE_GUNS) and os.path.exists(core.FILE_RANK)):
            st.info("좌측 사이드바에서 분대편성표/휴가/총기/짬표 엑셀을 모두 업로드해야 공정표를 생성할 수 있습니다.")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("#### Solver 옵션")
                n_calls = st.number_input("가중치 탐색 횟수 (tune_weights)", 5, 30, 12, 1)
                time_limit = st.number_input("CP-SAT 시간 제한 (초)", 10, 120, 25, 5)
                workers = st.number_input("병렬 worker 수", 1, 16, 8, 1)
                prob_th = st.slider("ML 힌트 threshold (없으면 랜덤)", 0.5, 0.9, 0.6, 0.05)

                run_btn = st.button("🚀 공정표 생성 실행", type="primary")

            with col2:
                st.markdown("#### 설명")
                st.write(
                    """
                    - `tune_weights`로 alpha/beta/… 가중치 자동 탐색 후  
                      최적 조합으로 한 번 더 최종 Solver 실행합니다.  
                    - ML 학습용 `ml.csv`가 없으면 자동으로 랜덤 힌트 모드로 진행됩니다.  
                    - 결과는 `월간` 시트 + 일자별 `MM-DD` 시트를 가진 엑셀로 저장됩니다.
                    """
                )

            if run_btn:
                # core.main() 대신, 여기서 직접 main 로직을 약식으로 재구성
                with st.spinner("CP-SAT Solver가 공정표를 생성 중입니다..."):
                    # 1) ML 모델 (없으면 None)
                    clf = core.train_prob_model("ml.csv")
                    members = core.load_members(core.FILE_SQUADS)
                    vac_set = core.parse_vacation_sheet(core.FILE_VAC, core.YEAR, core.MONTH, core.DAYS)
                    k15_set = core.load_k15_set(core.FILE_GUNS)
                    M = len(members)
                    is_vac = {(mi, d): int((members[mi], d) in vac_set) for mi in range(M) for d in range(1, core.DAYS + 1)}
                    is_k15 = {mi: int(members[mi] in k15_set) for mi in range(M)}

                    x_hints = core.generate_x_hints(
                        clf,
                        members,
                        core.YEAR,
                        core.MONTH,
                        core.DAYS,
                        is_vac,
                        is_k15,
                        DAY_SIZE=core.DAY_SIZE,
                        NIGHT_SIZE=core.NIGHT_SIZE,
                        prob_threshold=prob_th,
                    )
                    hints = {"x": x_hints}

                    best_w, hist = core.tune_weights(
                        core.build_model_fn,
                        n_calls=int(n_calls),
                        time_limit=int(time_limit),
                        workers=int(workers),
                    )
                    best_w["LAMBDA_WKND_SPREAD"] = 400

                    try:
                        hist.to_csv("weight_search_log.csv", index=False)
                    except Exception:
                        pass

                    res = core.solve_once(
                        core.build_model_fn, best_w, hints=hints, time_limit=int(time_limit), workers=int(workers)
                    )

                st.write("Solver status:", res["status"], "| feasible:", res["feasible"], "| obj:", res.get("obj"))

                if res.get("feasible", False) and "schedule" in res:
                    schedule = res["schedule"]
                    try:
                        rankbook = core.load_rankbook(core.FILE_RANK)
                    except Exception:
                        rankbook = None

                    core.export_schedule_to_excel(
                        schedule, members, core.OUT_PATH, core.YEAR, core.MONTH, core.DAYS, rankbook
                    )
                    core.save_rolling_context_from_schedule(
                        f"rolling_state_{core.YEAR}_{core.MONTH:02d}.json",
                        schedule,
                        members,
                        core.YEAR,
                        core.MONTH,
                        core.DAYS,
                    )

                    st.success("✅ 공정표 생성 완료!")

                    df_sched = schedule_to_df(schedule, members, core.DAYS)
                    st.markdown("#### 📋 생성된 공정표 (텍스트 뷰)")
                    st.dataframe(df_sched, use_container_width=True)

                    st.markdown("#### 📊 병사별 근무 통계")
                    stats = compute_stats(schedule, members, core.YEAR, core.MONTH, core.DAYS)
                    st.dataframe(stats, use_container_width=True)
                    st.bar_chart(
                        stats.set_index("이름")[["주간", "야간", "예비"]],
                        use_container_width=True,
                    )

                    st.markdown("#### 📁 엑셀 다운로드")
                    download_excel_from_path(core.OUT_PATH, "📥 공정표 엑셀 다운로드")

                else:
                    st.error("❌ 해를 찾지 못했습니다. 하드 제약 충돌 가능성이 있습니다.")

    # =========================
    # 🪖 2) 신병 투입 / 재배치 탭
    # =========================
    with tab_newcomer:
        st.subheader("🪖 신병 투입 · 기존 공정표 재배치")

        st.write(
            """
            - 이미 존재하는 공정표(엑셀)를 기준으로  
              **신병 투입 날짜 이후 구간만** 다시 재배치합니다.  
            - 휴가 / 교육(훈련) 구간은 그대로 유지합니다.  
            - 신병도 기존 인원과 동일한 규칙(야주 금지, 예비 3연속 금지 등)을 적용받습니다.  
            - 전제: 신병은 이미 `분대편성표.xlsx`에 추가되어 있다고 가정합니다.
            """
        )

        existing_file = st.file_uploader("기존 공정표 (월간 시트가 포함된 엑셀) 업로드", type=["xlsx"], key="existing_schedule")

        col1, col2, col3 = st.columns(3)
        with col1:
            join_day = st.number_input("신병 투입 시작 날짜 (D일)", 1, core.DAYS, 15, 1)
        with col2:
            squad_choice = st.selectbox("신병 분대 선택 (표시용)", ["1분대", "2분대", "3분대"])
        with col3:
            is_assistant = st.selectbox("신병 역할", ["부사수", "사수"]) == "부사수"

        if existing_file is None:
            st.info("기존 공정표 엑셀 파일을 먼저 업로드 해 주세요.")
        else:
            temp_existing_path = "existing_schedule.xlsx"
            with open(temp_existing_path, "wb") as f:
                f.write(existing_file.read())

            # 이름 목록 불러오기
            try:
                members = core.load_members(core.FILE_SQUADS)
            except Exception as e:
                st.error(f"분대편성표를 읽는 중 오류 발생: {e}")
                members = []

            if not members:
                st.warning("분대편성표에서 멤버를 불러올 수 없습니다. 좌측에서 엑셀을 다시 업로드해 주세요.")
            else:
                newcomer_name = st.selectbox("신병(또는 재배치 중심 인원) 이름 선택", members)

                run_new_btn = st.button("🚀 신병 투입 반영 공정표 재생성", type="primary")

                if run_new_btn:
                    with st.spinner("신병 투입 후 구간 재배치 Solver 실행 중..."):
                        # 1) 기존 스케줄 로드
                        existing_sched = core.load_schedule_from_excel(temp_existing_path, members, core.DAYS)

                        # 2) 힌트(locks) 구성: join_day 이전은 기존 스케줄 그대로 고정
                        locks = {"x": {}, "y": {}, "r": {}}
                        name2mi = {core.normalize_name(nm): i for i, nm in enumerate(members)}

                        for d in range(1, int(join_day)):
                            day_dict = existing_sched.get(d, {})
                            for nm in members:
                                tag = str(day_dict.get(nm, "")).strip()
                                mi = name2mi[core.normalize_name(nm)]

                                shift_char, label_idx = core._parse_shift_label(tag)
                                # D/N/R/V = Day/Night/Reserve/Vacation
                                if shift_char == "D":
                                    sidx = 0
                                    locks["x"][(mi, d, 0)] = 1
                                    locks["x"][(mi, d, 1)] = 0
                                    if label_idx is not None:
                                        for ell in range(3):
                                            locks["y"][(mi, d, 0, ell)] = int(ell == label_idx)
                                elif shift_char == "N":
                                    sidx = 1
                                    locks["x"][(mi, d, 0)] = 0
                                    locks["x"][(mi, d, 1)] = 1
                                    if label_idx is not None:
                                        for ell in range(3):
                                            locks["y"][(mi, d, 1, ell)] = int(ell == label_idx)
                                elif shift_char in ("R", "V") or tag == "":
                                    locks["x"][(mi, d, 0)] = 0
                                    locks["x"][(mi, d, 1)] = 0
                                    # 예비 고정도 하고 싶다면 아래 한 줄 활성화
                                    if shift_char == "R":
                                        locks["r"][(mi, d)] = 1

                        hints = {
                            "locks": locks,
                            "existing_schedule": existing_sched,
                            "training_ranges": [],  # 교육 구간 추가시 core.make_training_hints 이용 가능
                        }

                        # 3) 가중치(고정 값 사용 또는 간단 탐색)
                        base_w = {
                            "alpha": 10,
                            "beta": 1,
                            "gamma": 2,
                            "delta": 40,
                            "ZETA": 3,
                            "LAMBDA_DN": 200,
                            "LAMBDA_RES": 15,
                            "LAMBDA_WKND_SPREAD": 400,
                        }

                        res_new = core.solve_once(core.build_model_fn, base_w, hints=hints, time_limit=40, workers=8)

                    st.write("Solver status:", res_new["status"], "| feasible:", res_new["feasible"], "| obj:", res_new.get("obj"))
                    if res_new.get("feasible", False) and "schedule" in res_new:
                        schedule_new = res_new["schedule"]
                        st.success("✅ 신병 투입 이후 구간 재배치 완료!")

                        df_new = schedule_to_df(schedule_new, members, core.DAYS)
                        st.markdown("#### 📋 재배치된 공정표")
                        st.dataframe(df_new, use_container_width=True)

                        stats_new = compute_stats(schedule_new, members, core.YEAR, core.MONTH, core.DAYS)
                        st.markdown("#### 📊 병사별 근무 통계 (신병 투입 반영)")
                        st.dataframe(stats_new, use_container_width=True)
                        st.bar_chart(
                            stats_new.set_index("이름")[["주간", "야간", "예비"]],
                            use_container_width=True,
                        )

                        # 엑셀로도 저장
                        try:
                            rankbook = core.load_rankbook(core.FILE_RANK)
                        except Exception:
                            rankbook = None

                        out_repair = f"{core.YEAR}년_{core.MONTH:02d}월_공정표_신병재배치.xlsx"
                        core.export_schedule_to_excel(
                            schedule_new,
                            members,
                            out_repair,
                            core.YEAR,
                            core.MONTH,
                            core.DAYS,
                            rankbook,
                        )
                        st.markdown("#### 📁 엑셀 다운로드")
                        download_excel_from_path(out_repair, "📥 신병 투입 반영 공정표 엑셀 다운로드")
                    else:
                        st.error("❌ 재배치 해를 찾지 못했습니다. 제약이 너무 빡세거나 투입 날짜가 애매할 수 있습니다.")

    # =========================
    # ✏️ 3) 수동 수정 & 엑셀 다운로드
    # =========================
    with tab_edit:
        st.subheader("✏️ 공정표 수동 수정 · 엑셀 내보내기")

        st.write(
            """
            - 이미 생성된 공정표 엑셀 또는 상단 탭에서 만든 공정표를  
              **표 형태로 편집**하고, 수정본을 엑셀로 다시 받을 수 있습니다.  
            - 월간 시트만 수정/내보내기 합니다. (일자별 MM-DD 시트는 core.export_schedule_to_excel 사용 시 재생성)
            """
        )

        edit_source = st.radio(
            "수정 대상 선택",
            ["직접 엑셀 업로드", "현재 디렉토리의 최신 공정표 사용"],
            horizontal=True,
        )

        df_base = None
        members_base = []

        if edit_source == "직접 엑셀 업로드":
            up = st.file_uploader("수정할 공정표 엑셀 업로드", type=["xlsx"], key="edit_upload")
            if up is not None:
                temp_path = "edit_source.xlsx"
                with open(temp_path, "wb") as f:
                    f.write(up.read())
                if os.path.exists(core.FILE_SQUADS):
                    members_base = core.load_members(core.FILE_SQUADS)
                    sched_base = core.load_schedule_from_excel(temp_path, members_base, core.DAYS)
                    df_base = schedule_to_df(sched_base, members_base, core.DAYS)
        else:
            # 현재 디렉토리에서 가장 최근 공정표 파일 찾기
            candidates = [f for f in os.listdir(".") if f.endswith(".xlsx") and "공정표" in f]
            if not candidates:
                st.info("현재 디렉토리에 공정표 엑셀 파일이 없습니다. 먼저 공정표를 한 번 생성해 주세요.")
            else:
                candidates.sort(reverse=True)
                chosen = st.selectbox("사용할 공정표 파일 선택", candidates)
                if os.path.exists(core.FILE_SQUADS):
                    members_base = core.load_members(core.FILE_SQUADS)
                    sched_base = core.load_schedule_from_excel(chosen, members_base, core.DAYS)
                    df_base = schedule_to_df(sched_base, members_base, core.DAYS)

        if df_base is not None:
            st.markdown("#### ✏️ 공정표 편집 (셀 클릭하여 수정 가능)")
            edited_df = st.data_editor(
                df_base,
                use_container_width=True,
                num_rows="dynamic",
                key="schedule_editor",
            )

            if st.button("📥 수정본 엑셀 생성 & 다운로드"):
                schedule_edited = df_to_schedule(edited_df, core.DAYS)

                try:
                    rankbook = core.load_rankbook(core.FILE_RANK)
                except Exception:
                    rankbook = None

                out_path_edit = f"{core.YEAR}년_{core.MONTH:02d}월_공정표_수정본.xlsx"
                core.export_schedule_to_excel(
                    schedule_edited,
                    list(edited_df["이름"].astype(str)),
                    out_path_edit,
                    core.YEAR,
                    core.MONTH,
                    core.DAYS,
                    rankbook,
                )
                st.success("✅ 수정본 엑셀 생성 완료!")
                download_excel_from_path(out_path_edit, "📥 수정본 공정표 엑셀 다운로드")
        else:
            st.info("수정할 공정표를 먼저 불러와 주세요.")


if __name__ == "__main__":
    main()

