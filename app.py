import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io

import db
import logic

# ── Bootstrap ──────────────────────────────────────────────────────────────

db.init_db()
logic.seed_sample_data(db)

# ── Constants ──────────────────────────────────────────────────────────────

IP_LABELS = {"patent": "特許", "trademark": "商標", "design": "意匠"}
STATUS_LABELS = {"active": "有効", "completed": "完了", "abandoned": "放棄"}

st.set_page_config(
    page_title="IP期限管理システム",
    page_icon="⚖️",
    layout="wide",
)

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚖️ IP期限管理")
    page = st.radio(
        "ページ選択",
        ["ダッシュボード", "案件一覧", "案件登録", "期限管理"],
        label_visibility="collapsed",
    )

# ── Helpers ─────────────────────────────────────────────────────────────────

def badge(label: str, color: str) -> str:
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.8em'>{label}</span>"


def nearest_annual_fee_per_case(deadlines: list[dict]) -> list[dict]:
    """For patent annual fees, keep only the earliest per case."""
    seen = set()
    result = []
    for d in deadlines:
        key = (d["case_id"], "年金" in d["deadline_type"])
        if "年金" in d["deadline_type"]:
            if d["case_id"] not in seen:
                seen.add(d["case_id"])
                result.append(d)
        else:
            result.append(d)
    return result


def fmt_date(s):
    return s if s else "—"


def deadline_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ip_type_label"] = df["ip_type"].map(IP_LABELS)
    df["status_label"] = df.get("case_status", df.get("status", "")).map(STATUS_LABELS)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ダッシュボード
# ══════════════════════════════════════════════════════════════════════════════

if page == "ダッシュボード":
    st.header("ダッシュボード")

    today = date.today()
    overdue = db.list_upcoming_deadlines(overdue=True)
    next30 = db.list_upcoming_deadlines(days=30)
    next60 = [d for d in db.list_upcoming_deadlines(days=60)
              if d["due_date"] > (today + timedelta(days=30)).isoformat()]

    # Suppress duplicate annual fees in dashboard
    overdue = nearest_annual_fee_per_case(overdue)
    next30 = nearest_annual_fee_per_case(next30)
    next60 = nearest_annual_fee_per_case(next60)

    summary = db.get_status_summary()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🔴 期限超過", len(overdue))
    col2.metric("🟡 30日以内", len(next30))
    col3.metric("🟠 31〜60日", len(next60))
    col4.metric("有効案件", summary.get("active", 0))
    col5.metric("完了・放棄", summary.get("completed", 0) + summary.get("abandoned", 0))

    st.divider()

    def render_deadline_card(rows: list[dict], title: str, color: str):
        st.subheader(title)
        if not rows:
            st.info("該当なし")
            return
        for r in rows:
            ip_label = IP_LABELS.get(r["ip_type"], r["ip_type"])
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
                c1.markdown(f"**{r['case_number']}**")
                c2.markdown(r["title"])
                c3.markdown(f"{ip_label} | {r['client']}")
                c4.markdown(
                    f"<span style='color:{color};font-weight:bold'>{r['due_date']}</span> {r['deadline_type']}",
                    unsafe_allow_html=True,
                )

    render_deadline_card(overdue, "🔴 期限超過", "#e53e3e")
    render_deadline_card(next30, "🟡 30日以内の期限", "#d69e2e")
    render_deadline_card(next60, "🟠 31〜60日以内の期限", "#dd6b20")

    st.divider()
    st.subheader("案件ステータス別件数")
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("有効 (active)", summary.get("active", 0))
    sc2.metric("完了 (completed)", summary.get("completed", 0))
    sc3.metric("放棄 (abandoned)", summary.get("abandoned", 0))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: 案件一覧
# ══════════════════════════════════════════════════════════════════════════════

elif page == "案件一覧":
    st.header("案件一覧")

    with st.expander("フィルタ・検索", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        f_ip = fc1.selectbox("種別", ["すべて", "patent", "trademark", "design"],
                             format_func=lambda x: "すべて" if x == "すべて" else IP_LABELS[x])
        f_st = fc2.selectbox("ステータス", ["すべて", "active", "completed", "abandoned"],
                             format_func=lambda x: "すべて" if x == "すべて" else STATUS_LABELS[x])
        all_cases = db.list_cases()
        clients = sorted({c["client"] for c in all_cases})
        f_cl = fc3.selectbox("クライアント", ["すべて"] + clients)
        f_q = fc4.text_input("検索（番号・名称）")

    cases = db.list_cases(
        ip_type=None if f_ip == "すべて" else f_ip,
        status=None if f_st == "すべて" else f_st,
        client=None if f_cl == "すべて" else f_cl,
        search=f_q or None,
    )

    if not cases:
        st.info("条件に一致する案件がありません。")
    else:
        display_cols = ["case_number", "title", "ip_type", "client",
                        "filing_date", "registration_date", "status"]
        df = pd.DataFrame(cases)[display_cols].rename(columns={
            "case_number": "管理番号",
            "title": "案件名称",
            "ip_type": "種別",
            "client": "クライアント",
            "filing_date": "出願日",
            "registration_date": "登録日",
            "status": "ステータス",
        })
        df["種別"] = df["種別"].map(IP_LABELS)
        df["ステータス"] = df["ステータス"].map(STATUS_LABELS)

        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSVダウンロード", csv, "cases.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: 案件登録
# ══════════════════════════════════════════════════════════════════════════════

elif page == "案件登録":
    st.header("案件登録 / 編集 / 削除")

    # ── 既存案件の選択（編集・削除用）
    all_cases = db.list_cases()
    case_options = {f"{c['case_number']} - {c['title']}": c for c in all_cases}
    select_label = st.selectbox(
        "既存案件を選択して編集・削除（新規登録は空欄のまま）",
        ["（新規登録）"] + list(case_options.keys()),
    )

    prefill = {}
    editing_id = None
    if select_label != "（新規登録）":
        editing_id = case_options[select_label]["id"]
        prefill = case_options[select_label]

    def pf(key, default=None):
        return prefill.get(key, default)

    with st.form("case_form"):
        st.subheader("新規登録" if not editing_id else f"編集: {prefill['case_number']}")

        fc1, fc2 = st.columns(2)
        case_number = fc1.text_input("管理番号 *", value=pf("case_number", ""))
        title = fc2.text_input("案件名称 *", value=pf("title", ""))

        fc3, fc4 = st.columns(2)
        ip_type = fc3.selectbox(
            "種別 *",
            ["patent", "trademark", "design"],
            format_func=lambda x: IP_LABELS[x],
            index=["patent", "trademark", "design"].index(pf("ip_type", "patent")),
        )
        client = fc4.text_input("クライアント名 *", value=pf("client", ""))

        fd1, fd2, fd3 = st.columns(3)
        filing_date_val = pf("filing_date")
        priority_date_val = pf("priority_date")
        registration_date_val = pf("registration_date")

        filing_date = fd1.date_input(
            "出願日 *",
            value=date.fromisoformat(filing_date_val) if filing_date_val else date.today(),
        )
        priority_date = fd2.date_input(
            "優先日（任意）",
            value=date.fromisoformat(priority_date_val) if priority_date_val else None,
        )
        registration_date = fd3.date_input(
            "登録日（任意）",
            value=date.fromisoformat(registration_date_val) if registration_date_val else None,
        )

        status = st.selectbox(
            "ステータス",
            ["active", "completed", "abandoned"],
            format_func=lambda x: STATUS_LABELS[x],
            index=["active", "completed", "abandoned"].index(pf("status", "active")),
        )
        notes = st.text_area("備考", value=pf("notes", "") or "")

        sub1, sub2, sub3 = st.columns([2, 1, 1])
        submitted = sub1.form_submit_button("保存", type="primary", use_container_width=True)
        deleted = sub3.form_submit_button("削除", type="secondary", use_container_width=True,
                                          disabled=(editing_id is None))

    if submitted:
        if not case_number or not title or not client:
            st.error("管理番号・案件名称・クライアント名は必須です。")
        else:
            reg_str = registration_date.isoformat() if registration_date else None
            pri_str = priority_date.isoformat() if priority_date else None
            filing_str = filing_date.isoformat()

            if editing_id:
                db.update_case(
                    editing_id,
                    case_number=case_number,
                    title=title,
                    ip_type=ip_type,
                    client=client,
                    filing_date=filing_str,
                    priority_date=pri_str,
                    registration_date=reg_str,
                    status=status,
                    notes=notes or None,
                )
                st.success(f"案件「{case_number}」を更新しました。")
            else:
                case_id = db.insert_case(
                    case_number, title, ip_type, client, filing_str,
                    pri_str, reg_str, status, notes or None,
                )
                dl_rows = logic.generate_deadlines_for_case(ip_type, filing_str, reg_str)
                if dl_rows:
                    db.bulk_insert_deadlines(
                        [(case_id, t, d, n) for t, d, n in dl_rows]
                    )
                st.success(f"案件「{case_number}」を登録しました（期限 {len(dl_rows)} 件自動生成）。")
            st.rerun()

    if deleted and editing_id:
        case_num = prefill["case_number"]
        db.delete_case(editing_id)
        st.success(f"案件「{case_num}」を削除しました。")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: 期限管理
# ══════════════════════════════════════════════════════════════════════════════

elif page == "期限管理":
    st.header("期限管理")

    all_cases = db.list_cases()
    if not all_cases:
        st.info("案件が登録されていません。先に案件を登録してください。")
        st.stop()

    case_options = {f"{c['case_number']} - {c['title']}": c for c in all_cases}
    selected_label = st.selectbox("案件を選択", list(case_options.keys()))
    selected_case = case_options[selected_label]
    case_id = selected_case["id"]

    st.markdown(
        f"**種別:** {IP_LABELS.get(selected_case['ip_type'], '')} &nbsp;|&nbsp; "
        f"**クライアント:** {selected_case['client']} &nbsp;|&nbsp; "
        f"**ステータス:** {STATUS_LABELS.get(selected_case['status'], '')}",
        unsafe_allow_html=True,
    )
    st.divider()

    deadlines = db.list_deadlines_for_case(case_id)
    today_str = date.today().isoformat()

    if deadlines:
        st.subheader("期限一覧")

        # Group: overdue / upcoming / done
        overdue_dl = [d for d in deadlines if not d["is_done"] and d["due_date"] < today_str]
        upcoming_dl = [d for d in deadlines if not d["is_done"] and d["due_date"] >= today_str]
        done_dl = [d for d in deadlines if d["is_done"]]

        def render_deadline_rows(rows: list[dict], section: str):
            for dl in rows:
                days_left = (date.fromisoformat(dl["due_date"]) - date.today()).days
                if dl["is_done"]:
                    color = "#718096"
                    urgency = "✅"
                elif days_left < 0:
                    color = "#e53e3e"
                    urgency = "🔴"
                elif days_left <= 30:
                    color = "#d69e2e"
                    urgency = "🟡"
                elif days_left <= 60:
                    color = "#dd6b20"
                    urgency = "🟠"
                else:
                    color = "#38a169"
                    urgency = "🟢"

                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 1])
                    c1.markdown(urgency)
                    c2.markdown(f"**{dl['deadline_type']}**")
                    c3.markdown(
                        f"<span style='color:{color};font-weight:bold'>{dl['due_date']}</span>",
                        unsafe_allow_html=True,
                    )
                    c4.markdown(dl["notes"] or "")
                    new_done = c5.checkbox(
                        "完了",
                        value=bool(dl["is_done"]),
                        key=f"done_{dl['id']}",
                    )
                    if new_done != bool(dl["is_done"]):
                        db.update_deadline_done(dl["id"], new_done)
                        st.rerun()

                    # Delete button
                    if st.button("削除", key=f"del_dl_{dl['id']}", type="secondary"):
                        db.delete_deadline(dl["id"])
                        st.rerun()

        if overdue_dl:
            st.markdown("#### 🔴 期限超過")
            render_deadline_rows(overdue_dl, "overdue")

        if upcoming_dl:
            st.markdown("#### 今後の期限")
            render_deadline_rows(upcoming_dl, "upcoming")

        if done_dl:
            with st.expander(f"✅ 完了済み（{len(done_dl)} 件）"):
                render_deadline_rows(done_dl, "done")
    else:
        st.info("この案件に期限が登録されていません。")

    st.divider()
    st.subheader("期限を手動追加")

    with st.form("add_deadline_form"):
        nc1, nc2 = st.columns(2)
        new_type = nc1.text_input("期限種別 *", placeholder="例: 拒絶理由応答")
        new_due = nc2.date_input("期限日 *", value=date.today() + timedelta(days=30))
        new_notes = st.text_input("備考")
        add_btn = st.form_submit_button("追加", type="primary")

    if add_btn:
        if not new_type:
            st.error("期限種別を入力してください。")
        else:
            db.insert_deadline(case_id, new_type, new_due.isoformat(), new_notes or None)
            st.success(f"期限「{new_type}」を追加しました。")
            st.rerun()
