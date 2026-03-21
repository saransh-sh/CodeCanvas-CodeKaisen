(function () {
  const STORAGE_KEY = 'kaizen_theme';
  const DARK = 'dark';
  const LIGHT = 'light';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }

  function getSavedTheme() {
    return localStorage.getItem(STORAGE_KEY) || LIGHT;
  }

  function saveTheme(theme) {
    localStorage.setItem(STORAGE_KEY, theme);
  }

  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') || LIGHT;
  }

  applyTheme(getSavedTheme());

  function injectToggle() {
    if (document.getElementById('kz-theme-toggle')) return;

    const btn = document.createElement('button');
    btn.id = 'kz-theme-toggle';
    btn.setAttribute('aria-label', 'Toggle dark/light mode');
    btn.setAttribute('title', 'Toggle dark/light mode');

    function updateLabel() {
      const isDark = currentTheme() === DARK;
      btn.innerHTML = isDark ? '☀️ Light' : '🌙 Dark';
    }

    updateLabel();

    btn.addEventListener('click', () => {
      const next = currentTheme() === DARK ? LIGHT : DARK;
      applyTheme(next);
      saveTheme(next);
      updateLabel();

      if (window.Chart) {
        const textColor = next === DARK ? '#c0a0b8' : '#2c2433';
        const gridColor = next === DARK ? 'rgba(212,120,140,0.1)' : '#f0f0f0';
        Chart.defaults.color = textColor;
        Chart.defaults.borderColor = gridColor;
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

       const signout = header.querySelector('.btn-signout') || header.querySelector('.mode-buttons');
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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectToggle);
  } else {
    injectToggle();
  }
})();
