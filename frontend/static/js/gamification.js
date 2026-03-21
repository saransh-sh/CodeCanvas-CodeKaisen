(function () {
  const STORAGE_KEY = 'kaizen_gamified';
  const LEVEL_KEY   = 'kaizen_last_level';

  function isGamified() {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  }

  function setGamified(val) {
    localStorage.setItem(STORAGE_KEY, val ? 'true' : 'false');
  }

  function injectTogglePill() {
    if (document.getElementById('kz-gamify-toggle')) return;
    const btn = document.createElement('button');
    btn.id = 'kz-gamify-toggle';
    btn.setAttribute('aria-label', 'Toggle Gamification Mode');
    btn.setAttribute('title', 'Toggle Gamification Mode');
    btn.innerHTML = '🎮 Gamify';
    if (isGamified()) btn.classList.add('active');

    btn.addEventListener('click', () => {
      const next = !isGamified();
      setGamified(next);
      btn.classList.toggle('active', next);
      if (next) {
        showGamificationPanel();
      } else {
        hideGamificationPanel();
      }
    });

    let wrapper = document.querySelector('.kz-action-wrapper');
    if (!wrapper && document.querySelector('.kaizen-header')) {
       const header = document.querySelector('.kaizen-header');
       wrapper = document.createElement('div');
       wrapper.className = 'kz-action-wrapper';
       wrapper.style.display = 'flex';
       wrapper.style.gap = '8px';
       wrapper.style.alignItems = 'center';
       wrapper.style.flexWrap = 'wrap';
       const signout = header.querySelector('.btn-signout');
       if (signout) {
         header.insertBefore(wrapper, signout);
         wrapper.appendChild(signout);
       } else {
         header.appendChild(wrapper);
       }
    }

    if (wrapper) {
      wrapper.insertBefore(btn, wrapper.firstChild);
    } else {
      document.body.appendChild(btn);
    }
  }

  function buildPanelHTML(data) {
    const { xp, level, xpToNext, currentLevelXP, nextLevelXP, streak, longestStreak, habitRanks, achievements } = data;
    const xpInLevel = xp - currentLevelXP;
    const pct = xpToNext > 0 ? Math.min((xpInLevel / xpToNext) * 100, 100) : 100;

    const rankItems = habitRanks.map((h, i) => `
      <li class="kz-habit-rank-item">
        <span class="kz-rank-num">${i + 1}</span>
        <span style="flex:0 0 120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${h.name}</span>
        <div class="kz-rank-bar-wrap">
          <div class="kz-rank-bar-fill" style="width:${h.pct}%"></div>
        </div>
        <span style="font-size:0.78em;color:var(--text-muted);min-width:32px;text-align:right;">${h.pct}%</span>
      </li>`).join('');

    const achievementBadges = achievements && achievements.length > 0 ? achievements.map(a => `
      <span class="kz-achievement-badge ${a.unlocked ? 'unlocked' : 'locked'}" title="${a.description}">
        ${a.icon} ${a.name}
      </span>`).join('') : '';

    return `
      <div class="kz-gamify-header">
        <span class="kz-gamify-title">⚡ Your Progress</span>
        <div class="kz-gamify-badges">
          <span class="kz-level-badge">🏆 Level ${level}</span>
          ${streak > 0 ? `<span class="kz-streak-badge"><span class="kz-streak-flame">🔥</span>${streak} day streak</span>` : ''}
          ${longestStreak > 1 ? `<span class="kz-streak-badge" style="background:linear-gradient(135deg,#7c3aed,#a855f7);">🎯 Best: ${longestStreak} days</span>` : ''}
        </div>
      </div>
      <div class="kz-xp-section">
        <div class="kz-xp-label-row">
          <span>XP: <strong>${xp}</strong> / ${nextLevelXP}</span>
          <span><strong>${xpToNext} XP</strong> to level ${level + 1}</span>
        </div>
        <div class="kz-xp-bar-wrap">
          <div class="kz-xp-bar-fill" style="width:${pct}%"></div>
        </div>
      </div>
      ${achievementBadges ? `
      <div class="kz-achievements-section">
        <div style="font-size:0.78em;color:var(--text-muted);font-weight:bold;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:8px;">Achievements</div>
        <div class="kz-achievements-grid">${achievementBadges}</div>
      </div>` : ''}
      ${rankItems ? `
      <div style="margin-top:14px;">
        <div style="font-size:0.78em;color:var(--text-muted);font-weight:bold;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:6px;">Today's Habit Rankings</div>
        <ul class="kz-habit-rank-list">${rankItems}</ul>
      </div>` : ''}
      <div style="margin-top:14px;text-align:center;">
        <a href="/leaderboard.html" style="display:inline-block;padding:8px 20px;background:linear-gradient(135deg,#d4788c,#b85a6e);color:#fff;border-radius:8px;text-decoration:none;font-size:0.85em;font-weight:bold;">🏆 View Leaderboard</a>
      </div>
    `;
  }

  async function showGamificationPanel() {
    hideGamificationPanel();

    const panel = document.createElement('div');
    panel.id = 'kz-gamification-panel';
    panel.innerHTML = '<div style="color:var(--text-muted);font-size:0.85em;padding:8px;">Loading your stats…</div>';

    const container = document.querySelector('.container');
    if (!container) return;
    const firstSection = container.querySelector('.section, .page-header, h2');
    if (firstSection) {
      container.insertBefore(panel, firstSection);
    } else {
      container.appendChild(panel);
    }

    try {
      let xp = 0;
      let level = 0;
      let xpToNext = 0;
      let currentLevelXP = 0;
      let nextLevelXP = 0;
      let streak = 0;
      let longestStreak = 0;
      let habitRanks = [];
      let achievements = [];

      try {
        const xpData = await apiFetch('/api/analytics/xp-progress');
        xp = xpData.xp || 0;
        level = xpData.level || 0;
        xpToNext = xpData.xp_to_next || 0;
        currentLevelXP = xpData.current_level_xp || 0;
        nextLevelXP = xpData.next_level_xp || 0;
        streak = xpData.streak || 0;
        longestStreak = xpData.longest_streak || 0;
      } catch (_) {
        try {
          const todayData = await apiFetch('/api/analytics/today');
          xp = todayData.progress.reduce((acc, h) => acc + (h.spent || 0), 0) * 3;
          level = Math.floor(xp / 500);
          currentLevelXP = level * 500;
          nextLevelXP = (level + 1) * 500;
          xpToNext = nextLevelXP - xp;
          streak = 0;
        } catch (_2) {}
      }

      try {
        const achData = await apiFetch('/api/analytics/achievements');
        achievements = achData.achievements || [];
        const unlocked = achievements.filter(a => a.unlocked);
        const locked = achievements.filter(a => !a.unlocked).slice(0, 5);
        achievements = [...unlocked, ...locked];
      } catch (_) {}

      try {
        const todayData = await apiFetch('/api/analytics/today');
        const habits = todayData.progress || [];
        const maxPct = Math.max(...habits.map(h => h.target > 0 ? Math.round(h.spent / h.target * 100) : 0), 1);
        habitRanks = habits
          .map(h => ({
            name: h.name,
            pct: h.target > 0 ? Math.min(Math.round(h.spent / h.target * 100), 100) : 0,
          }))
          .sort((a, b) => b.pct - a.pct)
          .slice(0, 5);
      } catch (_) {}

      panel.innerHTML = buildPanelHTML({
        xp, level, xpToNext, currentLevelXP, nextLevelXP,
        streak, longestStreak, habitRanks, achievements
      });

      const prevLevel = localStorage.getItem(LEVEL_KEY);
      if (prevLevel !== null && level > parseInt(prevLevel, 10)) {
        showLevelUpNotification(level);
      }
      localStorage.setItem(LEVEL_KEY, String(level));

      checkForNewAchievements();
    } catch (e) {
      panel.innerHTML = '<div style="color:var(--text-muted);font-size:0.85em;padding:8px;">Could not load gamification data.</div>';
    }
  }

  async function checkForNewAchievements() {
    try {
      const result = await apiFetch('/api/analytics/check-achievements', {
        method: 'POST'
      });
      if (result.count > 0) {
        showAchievementNotification(result.newly_unlocked);
      }
    } catch (_) {
    }
  }

  function showAchievementNotification(achievements) {
    achievements.forEach((ach, index) => {
      setTimeout(() => {
        const notification = document.createElement('div');
        notification.className = 'kz-achievement-notification';
        notification.innerHTML = `
          <div class="kz-achievement-icon">${ach.icon}</div>
          <div class="kz-achievement-info">
            <div class="kz-achievement-title">Achievement Unlocked!</div>
            <div class="kz-achievement-name">${ach.name}</div>
            <div class="kz-achievement-xp">+${ach.xp_bonus} XP</div>
          </div>
        `;
        document.body.appendChild(notification);

        setTimeout(() => notification.classList.add('show'), 10);
        setTimeout(() => {
          notification.classList.remove('show');
          setTimeout(() => notification.remove(), 300);
        }, 4000);
      }, index * 500);
    });
  }

  function hideGamificationPanel() {
    const existing = document.getElementById('kz-gamification-panel');
    if (existing) existing.remove();
  }

  function showLevelUpNotification(newLevel) {
    const overlay = document.createElement('div');
    overlay.className = 'kz-level-up-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', 'Level Up!');
    overlay.innerHTML = `
      <div class="kz-level-up-content">
        <div class="kz-level-up-title">🎉 LEVEL UP!</div>
        <div class="kz-level-up-message">You reached Level ${newLevel}</div>
        <div class="kz-level-up-subtitle">Tap anywhere to continue</div>
      </div>
    `;
    overlay.addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
    setTimeout(() => { if (overlay.parentNode) overlay.remove(); }, 4000);
  }

  function showXPGainPopup(xpAmount, anchorEl) {
    const popup = document.createElement('div');
    popup.className = 'kz-xp-gain-popup';
    popup.textContent = `+${xpAmount} XP`;

    if (xpAmount >= 50) {
      popup.classList.add('xp-epic');
    } else if (xpAmount >= 20) {
      popup.classList.add('xp-large');
    } else if (xpAmount >= 10) {
      popup.classList.add('xp-medium');
    } else {
      popup.classList.add('xp-small');
    }

    const existingPopups = document.querySelectorAll('.kz-xp-gain-popup');
    const stackOffset = existingPopups.length * 45;

    popup.style.bottom = `calc(50vh - ${stackOffset}px)`;
    popup.style.left = '50%';
    popup.style.transform = 'translateX(-50%)';

    document.body.appendChild(popup);

    popup.addEventListener('animationend', () => popup.remove());
    setTimeout(() => { if (popup.parentNode) popup.remove(); }, 2000);
  }

  window.kzShowXPGain = showXPGainPopup;

  function init() {
    injectTogglePill();
    if (isGamified()) {
      setTimeout(showGamificationPanel, 600);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
