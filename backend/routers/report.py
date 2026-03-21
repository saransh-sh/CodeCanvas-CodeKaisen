from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from datetime import date, timedelta
from collections import defaultdict
import io

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable,
    )
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


def _fetch_report_data(uid: str, db) -> dict:
    today = date.today()

    one_year_ago = str(today - timedelta(days=364))
    summaries = list(
        db.collection("users").document(uid).collection("daily_summaries")
        .where("summary_date", ">=", one_year_ago)
        .order_by("summary_date")
        .stream()
    )
    score_map = {
        s.to_dict()["summary_date"]: s.to_dict()
        for s in summaries
        if "summary_date" in s.to_dict()
    }

    if score_map:
        start_date = date.fromisoformat(min(score_map.keys()))
    else:
        start_date = today - timedelta(days=6)

    total_days = (today - start_date).days + 1
    daily = []
    for i in range(total_days):
        d_str = str(start_date + timedelta(days=i))
        entry = score_map.get(d_str, {})
        daily.append({
            "date": d_str,
            "pct": entry.get("productivity_score", 0),
            "minutes": entry.get("total_completed_minutes", 0),
        })

    completion_rate = round(sum(d["pct"] for d in daily) / max(total_days, 1), 1)

    day_buckets: dict = defaultdict(list)
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for d in daily:
        day_buckets[date.fromisoformat(d["date"]).weekday()].append(d["pct"])

    best_day, best_day_pct = "N/A", 0.0
    worst_day, worst_day_pct = "N/A", 100.0
    for idx, scores in day_buckets.items():
        avg = sum(scores) / len(scores)
        if avg > best_day_pct:
            best_day_pct, best_day = round(avg, 1), DAY_NAMES[idx]
        if avg < worst_day_pct:
            worst_day_pct, worst_day = round(avg, 1), DAY_NAMES[idx]

    longest_streak = cur = 0
    for d in daily:
        if d["pct"] > 0:
            cur += 1
            longest_streak = max(longest_streak, cur)
        else:
            cur = 0
    user_doc = db.collection("users").document(uid).get()
    if user_doc.exists:
        longest_streak = max(longest_streak, user_doc.to_dict().get("longest_streak", 0))

    habits = list(db.collection("users").document(uid).collection("habits").stream())
    habit_streaks = []
    for h in habits:
        name = h.to_dict().get("name", "")
        streak = 0
        for i in range(365):
            day = str(today - timedelta(days=i))
            logs = list(
                db.collection("users").document(uid).collection("activity_logs")
                .where("log_date", "==", day).where("habit_name", "==", name).limit(1).stream()
            )
            if logs:
                streak += 1
            elif i == 0:
                continue
            else:
                break
        habit_streaks.append({"name": name, "streak": streak})
    habit_streaks.sort(key=lambda x: x["streak"], reverse=True)

    active_days = sum(1 for d in daily if d["pct"] > 0)
    consistency_score = round(active_days / max(total_days, 1) * 100, 1)
    active_scores = [d["pct"] for d in daily if d["pct"] > 0]
    performance_score = round(sum(active_scores) / max(len(active_scores), 1), 1)
    total_minutes = sum(d["minutes"] for d in daily)

    top_habit = habit_streaks[0]["name"] if habit_streaks else None
    needs_improvement = habit_streaks[-1]["name"] if len(habit_streaks) > 1 else None

    date_range_label = (
        f"Last {total_days} day{'s' if total_days != 1 else ''}"
        if total_days <= 30
        else f"All-time ({total_days} days)"
    )

    return {
        "daily": daily,
        "completion_rate": completion_rate,
        "best_day": best_day,
        "best_day_pct": best_day_pct,
        "worst_day": worst_day,
        "worst_day_pct": worst_day_pct,
        "longest_streak": longest_streak,
        "habit_streaks": habit_streaks[:8],
        "consistency_score": consistency_score,
        "performance_score": performance_score,
        "total_minutes": total_minutes,
        "total_habits": len(habits),
        "top_habit": top_habit,
        "needs_improvement": needs_improvement,
        "date_range_label": date_range_label,
        "total_days": total_days,
        "start_date": str(start_date),
        "end_date": str(today),
    }


def _score_color(pct: float) -> str:
    if pct >= 75:
        return "#22c55e"
    if pct >= 50:
        return "#f59e0b"
    return "#ef4444"


def _build_html_report(data: dict, user_name: str = "User") -> str:
    daily = data["daily"]
    habit_streaks = data["habit_streaks"]

    
    col_w = max(6, min(20, 680 // max(len(daily), 1)))
    bars = "".join(
        f'<td style="vertical-align:bottom;padding:0 1px;">'
        f'<div title="{d["date"]}: {d["pct"]}%"'
        f' style="width:{col_w}px;height:{max(2, round(d["pct"] * 0.8))}px;'
        f'background:{_score_color(d["pct"])};border-radius:2px 2px 0 0;"></div></td>'
        for d in daily
    )
    mini_chart = f'<table style="border-collapse:collapse;width:100%;"><tr style="height:80px;">{bars}</tr></table>'

  
    max_streak = max((h["streak"] for h in habit_streaks), default=1) or 1
    habit_bars = "".join(
        f'<div style="margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px;">'
        f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:240px;">{h["name"]}</span>'
        f'<span style="color:#b85a6e;font-weight:600;">🔥 {h["streak"]} days</span></div>'
        f'<div style="background:#f5ecee;border-radius:4px;height:8px;overflow:hidden;">'
        f'<div style="width:{round(h["streak"]/max_streak*100)}%;height:100%;background:#d4788c;border-radius:4px;"></div>'
        f'</div></div>'
        for h in habit_streaks
    ) or '<p style="color:#aaa;font-size:11px;">No habit data available.</p>'

    if daily:
        max_pct = max(d["pct"] for d in daily)
        min_pct = min(d["pct"] for d in daily)
        key = set()
        for i, d in enumerate(daily):
            if d["pct"] == max_pct or d["pct"] == min_pct:
                key.add(i)
        step = max(1, len(daily) // 10)
        for i in range(0, len(daily), step):
            key.add(i)
        DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        rows = "".join(
            f'<tr class="{"rpt-best-day" if daily[i]["pct"] == max_pct else "rpt-worst-day" if daily[i]["pct"] == min_pct and daily[i]["pct"] != max_pct else ""}">'
            f'<td><strong>{daily[i]["date"]}</strong> <span style="color:#aaa;font-size:10px;">'
            f'{DAY_SHORT[date.fromisoformat(daily[i]["date"]).weekday() % 7]}</span>'
            f'{"  ⭐ Best" if daily[i]["pct"] == max_pct else "  ⚠️ Worst" if daily[i]["pct"] == min_pct and daily[i]["pct"] != max_pct else ""}</td>'
            f'<td>{daily[i]["pct"]}%</td>'
            f'<td><div style="display:inline-block;width:{daily[i]["pct"]}%;height:6px;background:{_score_color(daily[i]["pct"])};border-radius:3px;vertical-align:middle;"></div></td>'
            f'</tr>'
            for i in sorted(key)
        )
    else:
        rows = '<tr><td colspan="3" style="color:#aaa;">No data available</td></tr>'

    perf = data["performance_score"]
    cons = data["consistency_score"]
    comp = data["completion_rate"]

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; color: #1a1a2e; padding: 48px 52px; }}
  .rpt-title {{ font-size: 24px; font-weight: bold; color: #d4788c; }}
  .rpt-subtitle {{ font-size: 13px; color: #555; }}
  .rpt-section-title {{ font-size: 15px; font-weight: bold; color: #b85a6e; border-left: 4px solid #d4788c; padding-left: 10px; margin: 0 0 14px; }}
  .rpt-stat-grid {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .rpt-stat-box {{ flex: 1; min-width: 100px; background: #fdf0f3; border: 1px solid #f0c8d4; border-radius: 10px; padding: 14px 10px; text-align: center; }}
  .rpt-stat-value {{ font-size: 22px; font-weight: bold; color: #b85a6e; }}
  .rpt-stat-label {{ font-size: 10px; color: #888; text-transform: uppercase; }}
  .rpt-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  .rpt-table th {{ background: #fdf0f3; color: #b85a6e; padding: 6px 10px; text-align: left; }}
  .rpt-table td {{ padding: 6px 10px; border-bottom: 1px solid #f5f0f2; }}
  .rpt-insight-list {{ list-style: none; padding: 0; }}
  .rpt-insight-list li {{ padding: 8px 12px; margin-bottom: 6px; background: #fdf0f3; border-left: 3px solid #d4788c; }}
  .rpt-tips-list li {{ margin-bottom: 6px; padding: 6px 10px; background: #fff8f0; border: 1px solid #f5e6d0; }}
  .rpt-footer {{ border-top: 1px solid #ddd; margin-top: 20px; padding-top: 10px; font-size: 10px; color: #aaa; text-align: center; }}
  .rpt-best-day {{ background: #f0fdf4; }}
  .rpt-worst-day {{ background: #fef2f2; }}
  .rpt-chart-wrap {{ background: #fafafa; border: 1px solid #e8e0e4; border-radius: 8px; padding: 12px; margin-bottom: 14px; }}
  .rpt-chart-title {{ font-size: 11px; font-weight: bold; color: #9b3a5c; text-transform: uppercase; margin-bottom: 8px; }}
  .rpt-section {{ margin-bottom: 28px; }}
  .rpt-header {{ border-bottom: 3px solid #d4788c; padding-bottom: 16px; margin-bottom: 24px; }}
  .score-pill {{ display:inline-block; padding:4px 12px; border-radius:20px; font-size:11px; font-weight:bold; margin-right:6px; }}
</style>
</head><body>
  <div class="rpt-header">
    <div class="rpt-title">📊 Productivity Report</div>
    <div class="rpt-subtitle">
      <strong>{user_name}</strong> &nbsp;·&nbsp; {data["date_range_label"]}
      ({data["start_date"]} – {data["end_date"]}) &nbsp;·&nbsp;
      Generated {date.today().strftime("%B %d, %Y")}
    </div>
  </div>

  <!-- Section 1: Summary -->
  <div class="rpt-section">
    <div class="rpt-section-title">Section 1 — Summary</div>
    <div class="rpt-stat-grid">
      <div class="rpt-stat-box">
        <div class="rpt-stat-value">{data["total_habits"]}</div>
        <div class="rpt-stat-label">Total Habits</div>
      </div>
      <div class="rpt-stat-box">
        <div class="rpt-stat-value">{data["total_minutes"] or "–"}</div>
        <div class="rpt-stat-label">Minutes Completed</div>
      </div>
      <div class="rpt-stat-box">
        <div class="rpt-stat-value">{comp}%</div>
        <div class="rpt-stat-label">Avg Productivity</div>
      </div>
      <div class="rpt-stat-box">
        <div class="rpt-stat-value">{data["longest_streak"]}</div>
        <div class="rpt-stat-label">Best Streak 🔥</div>
      </div>
      <div class="rpt-stat-box">
        <div class="rpt-stat-value">{perf}%</div>
        <div class="rpt-stat-label">Performance Score</div>
      </div>
      <div class="rpt-stat-box">
        <div class="rpt-stat-value">{cons}%</div>
        <div class="rpt-stat-label">Consistency Score</div>
      </div>
    </div>
    <p style="font-size:12px;color:#555;margin:0 0 8px;">
      🏆 <strong>Top Habit:</strong>
      {f'<span style="color:#22c55e;font-weight:bold;">{data["top_habit"]}</span>' if data["top_habit"] else "–"}
      &nbsp;·&nbsp;
      ⚠️ <strong>Needs Improvement:</strong>
      {f'<span style="color:#ef4444;">{data["needs_improvement"]}</span>' if data["needs_improvement"] else "–"}
    </p>
    <p style="font-size:12px;color:#555;margin:0;">
      📅 <strong>Best Day:</strong> {data["best_day"]} ({data["best_day_pct"]}%)
      &nbsp;·&nbsp;
      📉 <strong>Worst Day:</strong> {data["worst_day"]} ({data["worst_day_pct"]}%)
    </p>
  </div>

  <!-- Section 2: Charts -->
  <div class="rpt-section">
    <div class="rpt-section-title">Section 2 — Charts</div>
    <div class="rpt-chart-wrap">
      <div class="rpt-chart-title">📅 Daily Completion — {data["date_range_label"]}</div>
      {mini_chart}
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#aaa;margin-top:4px;">
        <span>{data["start_date"]}</span>
        <span style="color:#ef4444;">■ &lt;50%</span>
        <span style="color:#f59e0b;">■ 50–74%</span>
        <span style="color:#22c55e;">■ ≥75%</span>
        <span>{data["end_date"]}</span>
      </div>
    </div>
    <div class="rpt-chart-wrap">
      <div class="rpt-chart-title">🏅 Habit Distribution (streak lengths)</div>
      {habit_bars}
    </div>
  </div>

  <!-- Section 3: Activity History -->
  <div class="rpt-section">
    <div class="rpt-section-title">Section 3 — Activity History</div>
    <table class="rpt-table">
      <thead><tr><th>Date</th><th>Completion</th><th>Progress</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <!-- Section 4: Insights -->
  <div class="rpt-section">
    <div class="rpt-section-title">Section 4 — Insights</div>
    <ul class="rpt-insight-list">
      {"".join(f"<li>{ins}</li>" for ins in _generate_insights(data))}
    </ul>
  </div>

  <!-- Section 5: Tips -->
  <div class="rpt-section">
    <div class="rpt-section-title">Section 5 — Improvement Tips</div>
    <ol class="rpt-tips-list">
      {"".join(f"<li>{t}</li>" for t in _generate_tips(data))}
    </ol>
  </div>

  <div class="rpt-footer">
    Kaizen AI · Productivity Report · {data["date_range_label"]} · Generated {date.today().strftime("%B %d, %Y")}
  </div>
</body></html>"""


def _generate_insights(data: dict) -> list:
    insights = []
    daily = data.get("daily", [])
    habit_streaks = data.get("habit_streaks", [])

    if data["best_day"] != "N/A" and data["best_day_pct"] >= 60:
        insights.append(f'You are most productive on <strong>{data["best_day"]}s</strong> ({data["best_day_pct"]}% avg completion).')

    if data["worst_day"] != "N/A" and data["worst_day_pct"] < 40:
        insights.append(f'Performance drops on <strong>{data["worst_day"]}s</strong> — consider lighter habit loads that day.')

    if data["longest_streak"] >= 7:
        insights.append(f'Impressive {data["longest_streak"]}-day best streak! Keep the momentum going.')

    comp = data["completion_rate"]
    if comp >= 80:
        insights.append(f'Outstanding {comp}% overall completion rate — you are in the top tier!')
    elif comp < 40:
        insights.append(f'{comp}% completion rate — try reducing habit targets temporarily to build consistency.')

    cons = data["consistency_score"]
    if cons >= 80:
        insights.append('Excellent consistency! You show up nearly every day.')
    elif cons < 50:
        insights.append('Consistency is below 50% — focus on showing up daily, even for small sessions.')

    if data.get("trend") == "up":
        insights.append('Your productivity is trending upward this week. Excellent momentum!')
    elif data.get("trend") == "down":
        insights.append('A dip in the last 7 days detected. Review what disrupted your routine.')

    if habit_streaks:
        insights.append(f'Your strongest habit is <strong>{habit_streaks[0]["name"]}</strong> with a {habit_streaks[0]["streak"]}-day streak.')

    if len(habit_streaks) > 1:
        worst = min(habit_streaks, key=lambda h: h["streak"])
        if worst["streak"] < habit_streaks[0]["streak"]:
            insights.append(f'Your most skipped habit is <strong>{worst["name"]}</strong> — schedule it earlier in the day.')

    return insights or ["Keep logging your habits to unlock personalised insights!"]


def _generate_tips(data: dict) -> list:
    tips = []
    comp = data["completion_rate"]
    cons = data["consistency_score"]

    if comp < 60:
        tips.append("Start with 2–3 core habits per day — consistency matters more than volume.")
    if comp >= 80:
        tips.append("You are performing strongly. Challenge yourself by adding a new habit this month.")
    if data["longest_streak"] < 7:
        tips.append("Aim for a 7-day streak on at least one habit to build lasting momentum.")
    if data["best_day"] != "N/A":
        tips.append(f'Leverage your best day ({data["best_day"]}) by scheduling your hardest habits then.')
    if cons < 60:
        tips.append("Pair a new habit with an existing daily routine (habit stacking) to improve consistency.")
    tips.append("Review your progress every Sunday evening and set intentions for the week ahead.")
    return tips[:6]



@router.get("/report", response_class=HTMLResponse)
def get_report_html(uid: str = Depends(get_uid), db=Depends(get_db)):
    """Return a full HTML productivity report for the authenticated user."""
    data = _fetch_report_data(uid, db)
    html = _build_html_report(data)
    return HTMLResponse(content=html)


@router.get("/report/pdf")
def get_report_pdf(uid: str = Depends(get_uid), db=Depends(get_db)):
    """Return a PDF productivity report using ReportLab."""
    if not _REPORTLAB_AVAILABLE:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=501,
            detail="PDF generation requires 'reportlab'. Install it with: pip install reportlab",
        )

    data = _fetch_report_data(uid, db)
    daily = data["daily"]
    habit_streaks = data["habit_streaks"]

   
    user_doc = db.collection("users").document(uid).get()
    user_name = "User"
    if user_doc.exists:
        user_data = user_doc.to_dict()
        user_name = user_data.get("display_name") or user_data.get("email", "User")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    PINK = colors.HexColor("#d4788c")
    DARK_PINK = colors.HexColor("#b85a6e")
    BG_PINK = colors.HexColor("#fdf0f3")
    GREEN = colors.HexColor("#22c55e")
    AMBER = colors.HexColor("#f59e0b")
    RED = colors.HexColor("#ef4444")

    title_style = ParagraphStyle("title", fontSize=24, textColor=colors.HexColor("#1a1a2e"), fontName="Helvetica-Bold", spaceAfter=6, leading=28)
    sub_style = ParagraphStyle("sub", fontSize=11, textColor=colors.grey, spaceAfter=4, leading=14)
    sub_style2 = ParagraphStyle("sub2", fontSize=10, textColor=colors.grey, spaceAfter=12, leading=12)
    section_style = ParagraphStyle("section", fontSize=13, textColor=DARK_PINK, fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=10, leading=16)
    body_style = ParagraphStyle("body", fontSize=10, spaceAfter=6, leading=14)
    small_style = ParagraphStyle("small", fontSize=9, textColor=colors.grey, leading=12)

    story = []

    
    story.append(Paragraph(user_name, title_style))
    story.append(Paragraph("Kaizen AI Productivity Report", sub_style))
    story.append(Paragraph(
        f"{data['start_date']} – {data['end_date']}",
        sub_style2,
    ))
    story.append(Paragraph(
        f"Generated on: {date.today().strftime('%d %b %Y')}",
        sub_style2,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=PINK))
    story.append(Spacer(1, 10 * mm))

    # Summary stats table
    story.append(Paragraph("Summary", section_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Habits", str(data["total_habits"])],
        ["Minutes Completed", str(data["total_minutes"] or "–")],
        ["Avg Productivity", f"{data['completion_rate']}%"],
        ["Performance Score", f"{data['performance_score']}%"],
        ["Consistency Score", f"{data['consistency_score']}%"],
        ["Best Streak", f"{data['longest_streak']} days"],
        ["Best Day", f"{data['best_day']} ({data['best_day_pct']}%)"],
        ["Worst Day", f"{data['worst_day']} ({data['worst_day_pct']}%)"],
        ["Top Habit", data["top_habit"] or "–"],
        ["Needs Improvement", data["needs_improvement"] or "–"],
    ]
    tbl = Table(summary_data, colWidths=[80 * mm, 80 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PINK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 1), (-1, -1), BG_PINK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_PINK, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f0c8d4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6 * mm))

    # Habit streaks
    if habit_streaks:
        story.append(Paragraph("Performance Charts", section_style))
        streak_data = [["Habit", "Current Streak"]] + [
            [h["name"], f"{h['streak']} days"] for h in habit_streaks
        ]
        stbl = Table(streak_data, colWidths=[110 * mm, 50 * mm])
        stbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK_PINK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_PINK]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f0c8d4")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(stbl)
        story.append(Spacer(1, 6 * mm))

    # Activity history (sample)
    story.append(Paragraph("Activity History", section_style))
    if daily:
        key = set()
        max_pct = max(d["pct"] for d in daily)
        min_pct = min(d["pct"] for d in daily)
        for i, d in enumerate(daily):
            if d["pct"] == max_pct or d["pct"] == min_pct:
                key.add(i)
        step = max(1, len(daily) // 12)
        for i in range(0, len(daily), step):
            key.add(i)

        act_data = [["Date", "Completion %", "Note"]]
        DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for i in sorted(key):
            d = daily[i]
            note = "Best" if d["pct"] == max_pct else "Worst" if d["pct"] == min_pct and d["pct"] != max_pct else ""
            day_name = DAY_SHORT[date.fromisoformat(d["date"]).weekday() % 7]
            act_data.append([f'{d["date"]} ({day_name})', f'{d["pct"]}%', note])

        atbl = Table(act_data, colWidths=[65 * mm, 40 * mm, 55 * mm])
        row_colors = []
        for idx in range(1, len(act_data)):
            orig_i = sorted(key)[idx - 1]
            d = daily[orig_i]
            if d["pct"] == max_pct:
                row_colors.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#f0fdf4")))
            elif d["pct"] == min_pct and d["pct"] != max_pct:
                row_colors.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fef2f2")))

        atbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK_PINK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f0c8d4")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            *row_colors,
        ]))
        story.append(atbl)
        story.append(Spacer(1, 6 * mm))

    # Insights
    story.append(Paragraph("Insights", section_style))
    for ins in _generate_insights(data):
        # Strip basic HTML tags for PDF
        clean = ins.replace("<strong>", "").replace("</strong>", "").replace("<b>", "").replace("</b>", "")
        story.append(Paragraph(f"• {clean}", body_style))
    story.append(Spacer(1, 6 * mm))

    # Tips
    story.append(Paragraph("Recommendations", section_style))
    for i, tip in enumerate(_generate_tips(data), 1):
        story.append(Paragraph(f"{i}. {tip}", body_style))
    story.append(Spacer(1, 8 * mm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Kaizen AI · Productivity Report · {data['date_range_label']} · Generated {date.today().strftime('%B %d, %Y')}",
        small_style,
    ))

    doc.build(story)
    buf.seek(0)
    filename = f"kaizen-report-{date.today()}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
