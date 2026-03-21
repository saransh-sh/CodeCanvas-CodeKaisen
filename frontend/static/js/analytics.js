(function () {
  const container = document.getElementById('kz-advanced-analytics');
  if (!container) return;

  const PINK_PALETTE = ['#d4788c', '#b85a6e', '#e8a0b0', '#c0608c', '#9b3a5c'];

  function waitFor(fn, delay = 100) {
    if (typeof apiFetch === 'function' && typeof requireAuth === 'function') {
      fn();
    } else {
      setTimeout(() => waitFor(fn, delay), delay);
    }
  }

  function scoreColor(pct) {
    if (pct >= 75) return '#22c55e';
    if (pct >= 50) return '#f59e0b';
    return '#ef4444';
  }

  function generateInsights(data) {
    const insights = [];
    const { daily, best_day, best_day_pct, completion_rate, longest_streak, habit_streaks } = data;

    if (best_day && best_day_pct >= 70)
      insights.push(`📅 You are most consistent on <strong>${best_day}s</strong> (${best_day_pct}% avg)`);

    const midWeek = daily.slice(-14).filter((_, i) => [2, 3].includes(i % 7));
    const midAvg = midWeek.reduce((s, d) => s + d.pct, 0) / (midWeek.length || 1);
    if (midAvg < completion_rate - 15)
      insights.push(`📉 Your performance tends to drop mid-week — plan lighter habit loads on Wed/Thu`);

    if (longest_streak >= 7)
      insights.push(`🔥 Impressive ${longest_streak}-day best streak! Keep the momentum going`);

    if (completion_rate >= 80)
      insights.push(`⭐ Outstanding ${completion_rate}% overall completion rate — you're in the top tier!`);
    else if (completion_rate < 50)
      insights.push(`💡 ${completion_rate}% completion rate — try reducing habit targets temporarily to build consistency`);

    const weekends = daily.slice(-28).filter((_, i) => [5, 6].includes(i % 7));
    const weekendAvg = weekends.reduce((s, d) => s + d.pct, 0) / (weekends.length || 1);
    if (weekendAvg > completion_rate + 10)
      insights.push(`🎉 You actually perform better on weekends than weekdays — great self-discipline!`);

    if (habit_streaks && habit_streaks[0])
      insights.push(`🏆 Your strongest habit is <strong>${habit_streaks[0].name}</strong> with a ${habit_streaks[0].streak}-day streak`);

    if (habit_streaks && habit_streaks.length > 1) {
      const sorted = [...habit_streaks].sort((a, b) => a.streak - b.streak);
      const mostSkipped = sorted[0];
      const maxStreak = Math.max(...habit_streaks.map(h => h.streak));
      if (mostSkipped.streak < maxStreak)
        insights.push(`⚠️ Your most skipped habit is <strong>${mostSkipped.name}</strong> — consider scheduling it earlier in the day`);
    }

    return insights.length > 0 ? insights : ['💡 Keep logging your habits to unlock personalized insights!'];
  }

  function buildHeatmap(daily) {
    if (!daily || !daily.length) {
      return '<div class="kz-heatmap-grid">No data</div>';
    }
    const [y, m, d] = daily[0].date.split('-').map(Number);
    const firstDayOfWeek = new Date(y, m - 1, d).getDay();
    const paddingCells = Array(firstDayOfWeek).fill(null);
    const allCells = [...paddingCells, ...daily];

    const cells = allCells.map((d) => {
      if (!d) return `<div class="kz-heatmap-cell kz-heat-0" style="opacity:0;pointer-events:none;"></div>`;
      const heat = d.pct === 0 ? 0 : d.pct < 20 ? 1 : d.pct < 40 ? 2 : d.pct < 60 ? 3 : d.pct < 80 ? 4 : 5;
      return `<div class="kz-heatmap-cell kz-heat-${heat}" title="${d.date}: ${d.pct}% complete" data-date="${d.date}" data-pct="${d.pct}"></div>`;
    });

    const weeks = Math.ceil(allCells.length / 7);
    return `<div class="kz-heatmap-grid" style="grid-template-columns:repeat(${weeks}, 1fr); grid-template-rows: repeat(7, 1fr); grid-auto-flow: column;">${cells.join('')}</div>`;
  }

  async function renderAdvanced(user) {
    container.innerHTML = '<div style="color:var(--text-muted);font-size:0.85em;padding:8px;">Loading advanced analytics…</div>';

    try {
      const data = await apiFetch('/api/analytics/advanced');
      const { completion_rate, best_day, best_day_pct, longest_streak, daily, habit_streaks } = data;

      const insights = generateInsights(data);
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const gridColor = isDark ? 'rgba(212,120,140,0.1)' : '#f0f0f0';
      const textColor = isDark ? '#c0a0b8' : '#6b5e72';

      container.innerHTML = `
        <div class="kz-advanced-title">📊 Advanced Analytics</div>

        <div class="kz-stats-row" style="margin-bottom:16px;">
          <div class="kz-stat-box">
            <span class="kz-stat-value">${completion_rate}%</span>
            <span class="kz-stat-label">30-Day Completion</span>
          </div>
          <div class="kz-stat-box">
            <span class="kz-stat-value">${best_day || '–'}</span>
            <span class="kz-stat-label">Best Day (${best_day_pct || 0}%)</span>
          </div>
          <div class="kz-stat-box">
            <span class="kz-stat-value">${longest_streak}</span>
            <span class="kz-stat-label">Longest Streak 🔥</span>
          </div>
        </div>

        <div class="kz-chart-card" style="margin-bottom:14px;">
          <h4>📅 30-Day Daily Completion</h4>
          <div style="position:relative;height:250px;max-height:250px;">
            <canvas id="kz-bar-30"></canvas>
          </div>
        </div>

        <div class="kz-chart-card kz-heatmap-card" style="margin-bottom:14px;">
          <h4>🗓️ Contribution Heatmap (Last 30 Days)</h4>
          <div style="font-size:0.75em;color:var(--text-muted);margin-bottom:8px;">Each cell = one day. Darker = more completed.</div>
          ${buildHeatmap(daily)}
          <div style="display:flex;align-items:center;gap:6px;margin-top:8px;font-size:0.72em;color:var(--text-muted);">
            <span>Less</span>
            ${[0,1,2,3,4,5].map(l => `<div style="width:10px;height:10px;border-radius:2px;" class="kz-heat-${l}"></div>`).join('')}
            <span>More</span>
          </div>
        </div>

        <div class="kz-chart-card" style="margin-bottom:14px;">
          <h4>📆 Last 7 Days Breakdown</h4>
          <div class="kz-weekly-grid" id="kz-weekly-cards"></div>
        </div>

        ${habit_streaks && habit_streaks.length ? `
        <div class="kz-chart-card" style="margin-bottom:14px;">
          <h4>🏅 Per-Habit Streak Rankings</h4>
          <ul class="kz-habit-rank-list">
            ${habit_streaks.map((h, i) => `
              <li class="kz-habit-rank-item">
                <span class="kz-rank-num">${i + 1}</span>
                <span style="flex:0 0 150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${h.name}</span>
                <div class="kz-rank-bar-wrap">
                  <div class="kz-rank-bar-fill" style="width:${Math.min(h.streak / 30 * 100, 100)}%"></div>
                </div>
                <span style="font-size:0.78em;color:var(--text-muted);min-width:50px;text-align:right;">🔥 ${h.streak} days</span>
              </li>`).join('')}
          </ul>
        </div>` : ''}

        <div id="kz-insights-panel">
          <h4 style="margin:0 0 10px;font-size:0.9em;color:var(--accent-dark);">🤖 AI Insights</h4>
          <div id="kz-insights-chips"></div>
        </div>
      `;

      const last7 = daily.slice(-7);
      new Chart(document.getElementById('kz-bar-30'), {
        type: 'bar',
        data: {
          labels: daily.map(d => d.date.slice(5)),
          datasets: [{
            label: 'Completion %',
            data: daily.map(d => d.pct),
            backgroundColor: daily.map(d => scoreColor(d.pct) + 'cc'),
            borderColor: daily.map(d => scoreColor(d.pct)),
            borderWidth: 1,
            borderRadius: 4,
            borderSkipped: false,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => `${ctx.parsed.y}% complete` } },
          },
          scales: {
            y: { min: 0, max: 100, grid: { color: gridColor }, ticks: { color: textColor, font: { size: 9 } } },
            x: { grid: { display: false }, ticks: { color: textColor, font: { size: 8 }, maxRotation: 45, minRotation: 45, autoSkip: true, autoSkipPadding: 5, maxTicksLimit: 15 } },
          },
        },
      });

      const weeklyEl = document.getElementById('kz-weekly-cards');
      if (weeklyEl) {
        const last7days = daily.slice(-7);
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        weeklyEl.innerHTML = last7days.map(d => {
          const dayName = dayNames[new Date(d.date).getDay()];
          const color = d.pct >= 75 ? '#22c55e' : d.pct >= 50 ? '#f59e0b' : '#ef4444';
          return `
            <div class="kz-week-card">
              <div class="kz-week-day">${dayName}</div>
              <div class="kz-week-score" style="color:${color};">${d.pct}%</div>
              <div class="kz-week-label">${d.date.slice(5)}</div>
            </div>`;
        }).join('');
      }

      const chipsEl = document.getElementById('kz-insights-chips');
      if (chipsEl) {
        chipsEl.innerHTML = insights.map(insight =>
          `<span class="kz-insight-chip">💡 ${insight}</span>`
        ).join('');
      }

    } catch (e) {
      container.innerHTML = `<div class="kz-chart-card" style="color:var(--text-muted);font-size:0.85em;">
        Could not load advanced analytics. <a href="/activity.html">Add some habits and logs</a> to see your stats here.
      </div>`;
    }
  }

  waitFor(() => {
    requireAuth((user) => {
      setTimeout(() => renderAdvanced(user), 400);
    });
  });
})();
