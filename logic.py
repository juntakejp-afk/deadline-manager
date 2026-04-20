from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def compute_alerts(due_date_str: str):
    """Return (alert_90, alert_60, alert_30) as ISO strings from a due_date string."""
    due = date.fromisoformat(due_date_str)
    return (
        (due - timedelta(days=90)).isoformat(),
        (due - timedelta(days=60)).isoformat(),
        (due - timedelta(days=30)).isoformat(),
    )


def _add_years(d: date, years: int) -> date:
    return d + relativedelta(years=years)


def generate_deadlines_for_case(ip_type: str, filing_date, registration_date):
    """
    Returns list of (deadline_type, due_date_str, notes) tuples.
    filing_date and registration_date may be None or date/str objects.
    """
    rows = []

    def d(v):
        if v is None:
            return None
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    filing = d(filing_date)
    reg = d(registration_date)

    if ip_type == "patent":
        if filing:
            exam_due = _add_years(filing, 3)
            rows.append(("審査請求期限", exam_due.isoformat(), "特許法48条の3"))

        if reg:
            # 第1〜3年分（まとめて登録日+1年で表示）
            due_1_3 = _add_years(reg, 1)
            rows.append(("年金（第1〜3年）", due_1_3.isoformat(), "登録日+1年（まとめ納付）"))

            # 第4年〜第20年
            for n in range(4, 21):
                due = _add_years(reg, n)
                rows.append((f"年金（第{n}年）", due.isoformat(), None))

    elif ip_type == "trademark":
        if reg:
            renewal_10 = _add_years(reg, 10)
            rows.append(("更新期限（10年）", renewal_10.isoformat(), "商標法19条"))

            renewal_20 = _add_years(reg, 20)
            rows.append(("更新期限（20年）", renewal_20.isoformat(), "更新登録後の次回更新"))

    elif ip_type == "design":
        if reg:
            renewal_25 = _add_years(reg, 25)
            rows.append(("存続期間満了", renewal_25.isoformat(), "意匠法21条（25年）"))

    return rows


def seed_sample_data(db):
    """Insert sample cases+deadlines if DB is empty. db is the db module."""
    if db.list_cases():
        return

    today = date.today()

    samples = [
        {
            "case_number": "TKD-001",
            "title": "高効率太陽光発電システム",
            "ip_type": "patent",
            "client": "株式会社サンパワー",
            "filing_date": _add_years(today, -2).isoformat(),
            "priority_date": None,
            "registration_date": (today - timedelta(days=180)).isoformat(),
            "status": "active",
            "notes": "PCT出願予定",
        },
        {
            "case_number": "TKD-002",
            "title": "エコロジー（商標）",
            "ip_type": "trademark",
            "client": "グリーン株式会社",
            "filing_date": _add_years(today, -5).isoformat(),
            "priority_date": None,
            "registration_date": _add_years(today, -4).isoformat(),
            "status": "active",
            "notes": "第1類・第2類",
        },
        {
            "case_number": "TKD-003",
            "title": "多機能スマートウォッチ外観",
            "ip_type": "design",
            "client": "テック工業株式会社",
            "filing_date": _add_years(today, -1).isoformat(),
            "priority_date": None,
            "registration_date": (today - timedelta(days=60)).isoformat(),
            "status": "active",
            "notes": "部分意匠あり",
        },
    ]

    for s in samples:
        case_id = db.insert_case(
            s["case_number"], s["title"], s["ip_type"], s["client"],
            s["filing_date"], s["priority_date"], s["registration_date"],
            s["status"], s["notes"],
        )
        dl_rows = generate_deadlines_for_case(
            s["ip_type"], s["filing_date"], s["registration_date"]
        )
        db.bulk_insert_deadlines(
            [(case_id, t, d, n) for t, d, n in dl_rows]
        )
