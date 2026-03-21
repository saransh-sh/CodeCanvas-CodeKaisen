(function () {

  function todayStr() {
    return new Date().toISOString().slice(0, 10);
  }
  function thirtyDaysAgoStr() {
    const d = new Date();
    d.setDate(d.getDate() - 29);
    return d.toISOString().slice(0, 10);
  }
  function fmtDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function generateInsights(data) {
    const insights = [];
    const { daily = [], best_day, best_day_pct, worst_day, worst_day_pct,
            completion_rate, longest_streak, habit_streaks = [],
            consistency_score = 0, trend, date_range_label = '' } = data;

    if (best_day && best_day !== '–' && best_day_pct >= 60)
      insights.push(`You are most productive on <strong>${best_day}s</strong> (${best_day_pct}% avg completion)`);

    if (worst_day && worst_day !== '–' && worst_day_pct < 40)
      insights.push(`Performance drops on <strong>${worst_day}s</strong> — consider lighter habit loads that day`);

    const midWeek = daily.slice(-14).filter((_, i) => [2, 3].includes(i % 7));
    const midAvg = midWeek.reduce((s, d) => s + d.pct, 0) / (midWeek.length || 1);
    if (midWeek.length >= 2 && midAvg < completion_rate - 15)
      insights.push('Your performance tends to drop mid-week — consider lighter habit loads on Wed/Thu');

    if (longest_streak >= 7)
      insights.push(`Impressive ${longest_streak}-day best streak! Keep the momentum going`);

    if (completion_rate >= 80)
      insights.push(`Outstanding ${completion_rate}% overall completion rate — you are in the top tier!`);
    else if (completion_rate < 40)
      insights.push(`${completion_rate}% completion rate — try reducing habit targets temporarily to build consistency`);

    if (consistency_score >= 80)
      insights.push('Excellent consistency! You show up nearly every day.');
    else if (consistency_score < 50)
      insights.push('Consistency is below 50% — focus on showing up daily, even for short sessions.');

    if (trend === 'up')
      insights.push('Your productivity is trending upward this week. Excellent momentum!');
    else if (trend === 'down')
      insights.push('A dip in the last 7 days detected. Review what disrupted your routine.');

    if (habit_streaks[0])
      insights.push(`Your strongest habit is <strong>${habit_streaks[0].name}</strong> with a ${habit_streaks[0].streak}-day streak`);

    if (habit_streaks.length > 1) {
      const sorted = [...habit_streaks].sort((a, b) => a.streak - b.streak);
      const mostSkipped = sorted[0];
      if (mostSkipped.streak < sorted[sorted.length - 1].streak)
        insights.push(`Your most skipped habit is <strong>${mostSkipped.name}</strong> — consider scheduling it earlier in the day`);
    }

    return insights.length ? insights : ['Keep logging your habits to unlock personalised insights!'];
  }

  function generateTips(data) {
    const tips = [];
    const { completion_rate = 0, longest_streak = 0, best_day, daily = [], habit_streaks = [] } = data;

    if (completion_rate < 60)
      tips.push('Start with just 2-3 core habits per day — consistency matters more than volume.');
    if (completion_rate >= 80)
      tips.push('You are already performing strongly. Challenge yourself by adding a new habit this month.');
    if (longest_streak < 7)
      tips.push('Aim for a 7-day streak on at least one habit to build lasting momentum.');
    if (best_day)
      tips.push(`Leverage your best day (${best_day}) by scheduling your hardest habits then.`);

    if (daily.length >= 14) {
      const first7 = daily.slice(0, 7).reduce((s, d) => s + d.pct, 0) / 7;
      const last7  = daily.slice(-7).reduce((s, d) => s + d.pct, 0)  / 7;
      if (last7 > first7 + 10)
        tips.push('Your productivity is trending upward — keep the current routine going!');
      else if (last7 < first7 - 10)
        tips.push('Performance dropped in the last week. Review which habits you are missing most.');
    }

    if (habit_streaks.length > 1) {
      const sorted = [...habit_streaks].sort((a, b) => a.streak - b.streak);
      tips.push(`Give extra attention to "${sorted[0].name}" — it has the lowest streak right now.`);
    }

    tips.push('Review your progress every Sunday evening and set intentions for the week ahead.');
    tips.push('Pair a new habit with an existing one (habit stacking) to make it easier to remember.');

    return tips.slice(0, 6);
  }

  function scoreColor(pct) {
    if (pct >= 75) return '#22c55e';
    if (pct >= 50) return '#f59e0b';
    return '#ef4444';
  }

  function buildActivityRows(daily) {
    if (!daily || !daily.length) return '<tr><td colspan="3" style="color:#aaa;">No data</td></tr>';

    const maxPct = Math.max(...daily.map(d => d.pct));
    const minPct = Math.min(...daily.map(d => d.pct));

    const keyDays = new Set();
    daily.forEach((d, i) => {
      if (d.pct === maxPct || d.pct === minPct) keyDays.add(i);
    });
    const step = Math.max(1, Math.floor(daily.length / 8));
    for (let i = 0; i < daily.length; i += step) keyDays.add(i);

    const sorted = [...keyDays].sort((a, b) => a - b);
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    return sorted.map(i => {
      const d = daily[i];
      const isBest  = d.pct === maxPct;
      const isWorst = d.pct === minPct && d.pct !== maxPct;
      const cls = isBest ? 'rpt-best-day' : isWorst ? 'rpt-worst-day' : '';
      const badge = isBest ? ' ⭐ Best' : isWorst ? ' ⚠️ Worst' : '';
      const dayName = dayNames[new Date(d.date).getDay()];
      const bar = `<div style="display:inline-block;width:${d.pct}%;height:6px;background:${scoreColor(d.pct)};border-radius:3px;vertical-align:middle;"></div>`;
      return `<tr class="${cls}">
        <td><strong>${d.date}</strong> <span style="color:#aaa;font-size:10px;">${dayName}</span>${badge}</td>
        <td>${d.pct}%</td>
        <td>${bar}</td>
      </tr>`;
    }).join('');
  }

  function buildMiniBarChart(daily, maxHeight = 80) {
    if (!daily || !daily.length) return '';
    const colW = Math.max(8, Math.floor(680 / daily.length));
    const bars = daily.map(d => {
      const h = Math.max(2, Math.round((d.pct / 100) * maxHeight));
      return `<td style="vertical-align:bottom;padding:0 1px;">
        <div title="${d.date}: ${d.pct}%"
             style="width:${colW}px;height:${h}px;background:${scoreColor(d.pct)};border-radius:2px 2px 0 0;"></div>
      </td>`;
    }).join('');
    return `<table style="border-collapse:collapse;width:100%;">
      <tr style="height:${maxHeight}px;">${bars}</tr>
    </table>`;
  }

  function buildHabitBars(habitStreaks) {
    if (!habitStreaks || !habitStreaks.length) return '<p style="color:#aaa;font-size:11px;">No habit data available.</p>';
    const maxStreak = Math.max(...habitStreaks.map(h => h.streak), 1);
    return habitStreaks.map(h => {
      const pct = Math.round((h.streak / maxStreak) * 100);
      return `<div style="margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px;">
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:240px;">${h.name}</span>
          <span style="color:#b85a6e;font-weight:600;">🔥 ${h.streak} days</span>
        </div>
        <div style="background:#f5ecee;border-radius:4px;height:8px;overflow:hidden;">
          <div style="width:${pct}%;height:100%;background:#d4788c;border-radius:4px;"></div>
        </div>
      </div>`;
    }).join('');
  }

  function buildReportHTML(user, data) {
    const { completion_rate = 0, best_day = '–', best_day_pct = 0,
            longest_streak = 0, daily = [], habit_streaks = [],
            consistency_score = 0, performance_score = 0,
            top_habit = null, needs_improvement = null,
            worst_day = '–', worst_day_pct = 0,
            date_range_label = 'All available data',
            start_date = '', end_date = '' } = data;

    const userName    = (user && (user.displayName || user.email)) || 'User';
    const totalMins   = daily.reduce((s, d) => s + (d.minutes || d.total_minutes || d.completed_minutes || 0), 0);
    const totalHabits = (habit_streaks && habit_streaks.length) || 0;
    const dateRange   = start_date && end_date
      ? `${fmtDate(start_date)} – ${fmtDate(end_date)}`
      : `${fmtDate(thirtyDaysAgoStr())} – ${fmtDate(todayStr())}`;
    const insights    = generateInsights(data);
    const tips        = generateTips(data);
    const minsDisplay = totalMins > 0 ? totalMins : '–';

    return `
      <div class="rpt-header">
        <div class="rpt-title">📊 Productivity Report</div>
        <div class="rpt-subtitle">
          <strong>${userName}</strong> &nbsp;·&nbsp; ${date_range_label} (${dateRange}) &nbsp;·&nbsp; Generated ${new Date().toLocaleString()}
        </div>
      </div>

      <div class="rpt-section">
        <div class="rpt-section-title">Section 1 — Summary</div>
        <div class="rpt-stat-grid">
          <div class="rpt-stat-box">
            <div class="rpt-stat-value">${totalHabits}</div>
            <div class="rpt-stat-label">Total Habits</div>
          </div>
          <div class="rpt-stat-box">
            <div class="rpt-stat-value">${minsDisplay}</div>
            <div class="rpt-stat-label">Minutes Completed</div>
          </div>
          <div class="rpt-stat-box">
            <div class="rpt-stat-value">${completion_rate}%</div>
            <div class="rpt-stat-label">Avg Productivity</div>
          </div>
          <div class="rpt-stat-box">
            <div class="rpt-stat-value">${longest_streak}</div>
            <div class="rpt-stat-label">Best Streak 🔥</div>
          </div>
          <div class="rpt-stat-box">
            <div class="rpt-stat-value">${performance_score}%</div>
            <div class="rpt-stat-label">Performance Score</div>
          </div>
          <div class="rpt-stat-box">
            <div class="rpt-stat-value">${consistency_score}%</div>
            <div class="rpt-stat-label">Consistency Score</div>
          </div>
        </div>
        <p style="font-size:12px;color:#555;margin:0 0 6px;">
          🏆 <strong>Top Habit:</strong>
          ${top_habit ? `<span style="color:#22c55e;font-weight:bold;">${top_habit}</span>` : '–'}
          &nbsp;·&nbsp;
          ⚠️ <strong>Needs Improvement:</strong>
          ${needs_improvement ? `<span style="color:#ef4444;">${needs_improvement}</span>` : '–'}
        </p>
        <p style="font-size:12px;color:#555;margin:0;">
          📅 <strong>Best Day:</strong> ${best_day} (${best_day_pct}%)
          &nbsp;·&nbsp;
          📉 <strong>Worst Day:</strong> ${worst_day} (${worst_day_pct}%)
        </p>
      </div>

      <div class="rpt-section">
        <div class="rpt-section-title">Section 2 — Charts</div>

        <div class="rpt-chart-wrap">
          <div class="rpt-chart-title">📅 Daily Completion — ${date_range_label}</div>
          ${buildMiniBarChart(daily)}
          <div style="display:flex;justify-content:space-between;font-size:10px;color:#aaa;margin-top:4px;">
            <span>${fmtDate(start_date || thirtyDaysAgoStr())}</span>
            <span style="color:#ef4444;">■ &lt;50%</span>
            <span style="color:#f59e0b;">■ 50-74%</span>
            <span style="color:#22c55e;">■ ≥75%</span>
            <span>${fmtDate(end_date || todayStr())}</span>
          </div>
        </div>

        <div class="rpt-chart-wrap">
          <div class="rpt-chart-title">🏅 Habit Distribution (streak lengths)</div>
          ${buildHabitBars(habit_streaks)}
        </div>

        <div class="rpt-chart-wrap" style="background:#f5fdf8;">
          <div class="rpt-chart-title">📈 Recent Trend (last 14 days)</div>
          <div style="font-size:11px;color:#555;margin-bottom:8px;">
            Best day: <strong style="color:#22c55e;">${best_day} (${best_day_pct}%)</strong> &nbsp;·&nbsp;
            Average: <strong style="color:#d4788c;">${completion_rate}%</strong>
          </div>
          ${buildMiniBarChart(daily.slice(-14), 60)}
        </div>
      </div>

      <div class="rpt-section">
        <div class="rpt-section-title">Section 3 — Activity History</div>
        <table class="rpt-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Completion</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>${buildActivityRows(daily)}</tbody>
        </table>
      </div>

      <div class="rpt-section">
        <div class="rpt-section-title">Section 4 — AI Insights</div>
        <ul class="rpt-insight-list">
          ${insights.map(ins => `<li>${ins}</li>`).join('')}
        </ul>
      </div>

      <div class="rpt-section">
        <div class="rpt-section-title">Section 5 — Improvement Tips</div>
        <ol class="rpt-tips-list">
          ${tips.map(t => `<li>${t}</li>`).join('')}
        </ol>
      </div>

      <div class="rpt-footer">
        Kaizen AI · Productivity Report · ${date_range_label} · Generated ${new Date().toLocaleDateString()}
      </div>
    `;
  }

  async function exportPDF(user) {
    const token = await user.getIdToken();
    const response = await fetch('/api/report/pdf', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kaizen-report-${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
  }
  function attachButtons(wrap, user) {
    wrap.innerHTML = `
      <button class="kz-export-btn" id="kz-btn-pdf" title="Download PDF productivity report">
        ⬇ Export PDF Report
      </button>
    `;

    async function handleExport() {
      const pdfBtn = document.getElementById('kz-btn-pdf');
      if (pdfBtn) pdfBtn.disabled = true;
      if (pdfBtn) pdfBtn.textContent = '⏳ Generating…';

      try {
        await exportPDF(user);
      } catch (err) {
        console.error('[KaizenReport] Export failed:', err);
        alert('Could not generate report. Please ensure you have some activity logged.');
      } finally {
        if (pdfBtn) { pdfBtn.disabled = false; pdfBtn.innerHTML = '⬇ Export PDF Report'; }
      }
    }

    document.getElementById('kz-btn-pdf').addEventListener('click', handleExport);
  }

  function init() {
    const wrap = document.getElementById('kz-export-btn-wrap');
    if (!wrap) return;

    function waitFor(fn, delay = 100) {
      if (typeof apiFetch === 'function' && typeof requireAuth === 'function') {
        fn();
      } else {
        setTimeout(() => waitFor(fn, delay), delay);
      }
    }

    waitFor(() => {
      requireAuth((user) => {
        attachButtons(wrap, user);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
