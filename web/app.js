/**
 * Disney Comics Agenda — Minimalist Web App
 * Features:
 * - English language throughout
 * - Country dropdown filter
 * - Monthly Calendar Grid View + Chronological List View
 * - Clean, emoji-free typography & SVG icons
 * - Lightbox modal with cover and release details
 */

(function () {
  'use strict';

  // Global State
  let allReleases = [];
  let availableCountries = [];
  let activeCountry = 'all';
  let activeStatus = 'all'; // 'all', 'upcoming', 'released'
  let activeView = 'calendar'; // 'calendar', 'list'
  let searchQuery = '';

  // Calendar State
  const now = new Date();
  let calYear = now.getFullYear();
  let calMonth = now.getMonth(); // 0-indexed (0 = Jan, 10 = Nov)

  // DOM Elements
  const countrySelectEl = document.getElementById('country-select');
  const resultsCountEl = document.getElementById('results-count');
  const releasesCountBadgeEl = document.getElementById('releases-count-badge');
  const searchInputEl = document.getElementById('search-input');
  const clearSearchBtn = document.getElementById('clear-search');
  const resetFiltersBtn = document.getElementById('reset-filters-btn');
  const lastUpdateEl = document.getElementById('last-update');
  const themeToggleBtn = document.getElementById('theme-toggle');

  // View Containers
  const calendarViewEl = document.getElementById('calendar-view');
  const listViewEl = document.getElementById('list-view');
  const agendaContainerEl = document.getElementById('agenda-container');
  const emptyStateEl = document.getElementById('empty-state');
  const viewCalendarBtn = document.getElementById('view-calendar-btn');
  const viewListBtn = document.getElementById('view-list-btn');

  // Calendar Controls
  const calMonthTitleEl = document.getElementById('cal-month-title');
  const calPrevBtn = document.getElementById('cal-prev-btn');
  const calNextBtn = document.getElementById('cal-next-btn');
  const calTodayBtn = document.getElementById('cal-today-btn');
  const calMonthCountEl = document.getElementById('cal-month-count');
  const calendarDaysGridEl = document.getElementById('calendar-days-grid');

  // Modal Elements
  const modalEl = document.getElementById('cover-modal');
  const modalImgEl = document.getElementById('modal-image');
  const modalCaptionEl = document.getElementById('modal-caption');
  const modalCloseBtn = modalEl.querySelector('.modal-close');
  const modalBackdrop = modalEl.querySelector('.modal-backdrop');

  const MONTHS_EN = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  /**
   * Theme Management
   */
  function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
    }
    themeToggleBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      let target = 'light';
      if (!current) {
        const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        target = isSystemDark ? 'light' : 'dark';
      } else {
        target = current === 'dark' ? 'light' : 'dark';
      }
      document.documentElement.setAttribute('data-theme', target);
      localStorage.setItem('theme', target);
    });
  }

  /**
   * Fetch data from releases.json
   */
  async function loadData() {
    try {
      let response = await fetch('data/releases.json').catch(() => null);
      if (!response || !response.ok) {
        response = await fetch('releases.json').catch(() => null);
      }
      if (!response || !response.ok) {
        response = await fetch('https://raw.githubusercontent.com/WizyxGH/disney-comics-watcher/datas/releases.json');
      }
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      allReleases = data.releases || [];
      availableCountries = data.countries || [];

      // Update header badges
      releasesCountBadgeEl.textContent = `${allReleases.length} releases`;
      if (data.generated_at) {
        const dt = new Date(data.generated_at);
        lastUpdateEl.textContent = `Updated: ${dt.toLocaleDateString('en-US', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        })}`;
      }

      // Check URL query parameters
      const urlParams = new URLSearchParams(window.location.search);
      const urlCountry = urlParams.get('country');
      if (urlCountry && availableCountries.some(c => c.code.toLowerCase() === urlCountry.toLowerCase())) {
        activeCountry = urlCountry.toLowerCase();
      }

      const urlView = urlParams.get('view');
      if (urlView === 'list' || urlView === 'calendar') {
        activeView = urlView;
      }

      // Initialize calendar year/month with either today's month
      // or the closest month with upcoming releases
      initInitialCalendarDate();

      renderCountryDropdown();
      updateViewSwitchUI();
      renderCurrentView();
    } catch (err) {
      console.error('Failed to load releases data:', err);
      calendarViewEl.style.display = 'none';
      listViewEl.style.display = 'none';
      emptyStateEl.style.display = 'block';
      emptyStateEl.innerHTML = `
        <h3>Unable to load releases data</h3>
        <p>${escapeHtml(err.message)}</p>
      `;
    }
  }

  /**
   * Pick smart initial calendar month (current month or first upcoming)
   */
  function initInitialCalendarDate() {
    const todayStr = new Date().toISOString().slice(0, 10);
    // Find first upcoming or today release
    const upcoming = allReleases.find(r => r.date && r.date >= todayStr);
    if (upcoming && upcoming.date) {
      const [y, m] = upcoming.date.split('-');
      calYear = parseInt(y, 10);
      calMonth = parseInt(m, 10) - 1;
    } else {
      calYear = now.getFullYear();
      calMonth = now.getMonth();
    }
  }

  /**
   * Render Country Filter Dropdown
   */
  function renderCountryDropdown() {
    countrySelectEl.innerHTML = '';

    const allOpt = document.createElement('option');
    allOpt.value = 'all';
    allOpt.textContent = `All countries (${allReleases.length})`;
    allOpt.selected = activeCountry === 'all';
    countrySelectEl.appendChild(allOpt);

    availableCountries.forEach(country => {
      const opt = document.createElement('option');
      opt.value = country.code;
      opt.textContent = `${country.name} (${country.count})`;
      opt.selected = activeCountry === country.code;
      countrySelectEl.appendChild(opt);
    });

    countrySelectEl.addEventListener('change', (e) => {
      setCountry(e.target.value);
    });
  }

  function setCountry(code) {
    activeCountry = code;
    countrySelectEl.value = code;

    const url = new URL(window.location);
    if (code === 'all') {
      url.searchParams.delete('country');
    } else {
      url.searchParams.set('country', code);
    }
    window.history.replaceState({}, '', url);

    renderCurrentView();
  }

  /**
   * View Switch Handling (Calendar vs List)
   */
  function setView(view) {
    activeView = view;
    updateViewSwitchUI();

    const url = new URL(window.location);
    if (view === 'calendar') {
      url.searchParams.delete('view');
    } else {
      url.searchParams.set('view', view);
    }
    window.history.replaceState({}, '', url);

    renderCurrentView();
  }

  function updateViewSwitchUI() {
    viewCalendarBtn.classList.toggle('active', activeView === 'calendar');
    viewCalendarBtn.setAttribute('aria-selected', activeView === 'calendar');

    viewListBtn.classList.toggle('active', activeView === 'list');
    viewListBtn.setAttribute('aria-selected', activeView === 'list');

    if (activeView === 'calendar') {
      calendarViewEl.style.display = 'block';
      listViewEl.style.display = 'none';
    } else {
      calendarViewEl.style.display = 'none';
      listViewEl.style.display = 'block';
    }
  }

  viewCalendarBtn.addEventListener('click', () => setView('calendar'));
  viewListBtn.addEventListener('click', () => setView('list'));

  /**
   * Status Tabs & Search Handlers
   */
  document.querySelectorAll('.filter-status .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-status .tab-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      activeStatus = btn.dataset.status;
      renderCurrentView();
    });
  });

  searchInputEl.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    clearSearchBtn.style.display = searchQuery ? 'block' : 'none';
    renderCurrentView();
  });

  clearSearchBtn.addEventListener('click', () => {
    searchInputEl.value = '';
    searchQuery = '';
    clearSearchBtn.style.display = 'none';
    renderCurrentView();
    searchInputEl.focus();
  });

  resetFiltersBtn.addEventListener('click', () => {
    activeCountry = 'all';
    activeStatus = 'all';
    searchQuery = '';
    searchInputEl.value = '';
    clearSearchBtn.style.display = 'none';
    countrySelectEl.value = 'all';

    document.querySelectorAll('.filter-status .tab-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.status === 'all');
      b.setAttribute('aria-selected', b.dataset.status === 'all');
    });

    const url = new URL(window.location);
    url.searchParams.delete('country');
    url.searchParams.delete('view');
    window.history.replaceState({}, '', url);

    renderCurrentView();
  });

  /**
   * Filter releases according to selected country, status, and search
   */
  function getFilteredReleases() {
    return allReleases.filter(release => {
      if (activeCountry !== 'all' && release.country !== activeCountry) {
        return false;
      }
      if (activeStatus !== 'all' && release.status !== activeStatus) {
        return false;
      }
      if (searchQuery) {
        const fullText = [
          release.title,
          release.publisher,
          release.country_name,
          release.issue_code,
          release.ean
        ].filter(Boolean).join(' ').toLowerCase();
        if (!fullText.includes(searchQuery)) {
          return false;
        }
      }
      return true;
    });
  }

  function renderCurrentView() {
    const filtered = getFilteredReleases();
    if (activeView === 'calendar') {
      renderMonthlyCalendar(filtered);
    } else {
      renderListView(filtered);
    }
  }

  /**
   * ==========================================
   * MONTHLY CALENDAR VIEW
   * ==========================================
   */
  calPrevBtn.addEventListener('click', () => {
    calMonth--;
    if (calMonth < 0) {
      calMonth = 11;
      calYear--;
    }
    renderMonthlyCalendar(getFilteredReleases());
  });

  calNextBtn.addEventListener('click', () => {
    calMonth++;
    if (calMonth > 11) {
      calMonth = 0;
      calYear++;
    }
    renderMonthlyCalendar(getFilteredReleases());
  });

  calTodayBtn.addEventListener('click', () => {
    calYear = now.getFullYear();
    calMonth = now.getMonth();
    renderMonthlyCalendar(getFilteredReleases());
  });

  function renderMonthlyCalendar(filtered) {
    calMonthTitleEl.textContent = `${MONTHS_EN[calMonth]} ${calYear}`;

    // Target Year-Month prefix: "YYYY-MM"
    const ymPrefix = `${calYear}-${String(calMonth + 1).padStart(2, '0')}`;

    // Group releases by exact date "YYYY-MM-DD"
    const releasesByDate = {};
    let monthReleasesCount = 0;

    filtered.forEach(item => {
      if (!item.date) return;
      if (item.date.startsWith(ymPrefix)) {
        monthReleasesCount++;
        if (!releasesByDate[item.date]) {
          releasesByDate[item.date] = [];
        }
        releasesByDate[item.date].push(item);
      }
    });

    calMonthCountEl.textContent = `${monthReleasesCount} release${monthReleasesCount !== 1 ? 's' : ''}`;

    // Compute Calendar Days
    // First day of month
    const firstDay = new Date(calYear, calMonth, 1);
    // JS getDay(): 0 = Sun, 1 = Mon ... We want 0 = Mon, 6 = Sun
    let startDayOfWeek = (firstDay.getDay() + 6) % 7;

    // Total days in current month
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

    // Days in previous month
    const daysInPrevMonth = new Date(calYear, calMonth, 0).getDate();

    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

    let html = '';

    // 1. Preceding days from previous month
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const dayNum = daysInPrevMonth - i;
      html += `
        <div class="cal-day-cell cal-day-outside">
          <span class="cal-day-num">${dayNum}</span>
        </div>
      `;
    }

    // 2. Days of current month
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${ymPrefix}-${String(d).padStart(2, '0')}`;
      const isToday = dateStr === todayStr;
      const dayReleases = releasesByDate[dateStr] || [];
      const hasReleases = dayReleases.length > 0;

      html += `
        <div class="cal-day-cell ${isToday ? 'cal-day-today' : ''} ${hasReleases ? 'cal-day-has-events' : ''}">
          <div class="cal-day-header">
            <span class="cal-day-num ${isToday ? 'badge-today' : ''}">${d}</span>
            ${hasReleases ? `<span class="cal-day-event-count">${dayReleases.length}</span>` : ''}
          </div>
          <div class="cal-events-stack">
            ${dayReleases.map(renderCalendarEventPill).join('')}
          </div>
        </div>
      `;
    }

    // 3. Trailing days from next month to fill grid
    const totalRendered = startDayOfWeek + daysInMonth;
    const remaining = (7 - (totalRendered % 7)) % 7;
    for (let j = 1; j <= remaining; j++) {
      html += `
        <div class="cal-day-cell cal-day-outside">
          <span class="cal-day-num">${j}</span>
        </div>
      `;
    }

    calendarDaysGridEl.innerHTML = html;

    // Attach click listeners to calendar event pills for lightbox modal
    calendarDaysGridEl.querySelectorAll('.cal-event-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        const id = pill.dataset.id;
        const item = allReleases.find(r => r.id === id);
        if (item) {
          openReleaseModal(item);
        }
      });
    });
  }

  function renderCalendarEventPill(item) {
    const isUpcoming = item.status === 'upcoming';
    const statusClass = isUpcoming ? 'event-upcoming' : 'event-released';
    const countryCode = (item.country || '').toUpperCase();
    const coverUrl = item.cover_url || '';

    return `
      <div class="cal-event-pill ${statusClass}" data-id="${escapeHtml(item.id)}" title="${escapeHtml(item.title)} — ${escapeHtml(item.publisher || item.country_name)}">
        <div class="pill-thumb">
          ${coverUrl ? `<img src="${escapeHtml(coverUrl)}" alt="" loading="lazy">` : `<span class="thumb-empty"></span>`}
        </div>
        <div class="pill-info">
          <span class="pill-country">${countryCode}</span>
          <span class="pill-title">${escapeHtml(item.title)}</span>
        </div>
      </div>
    `;
  }

  /**
   * ==========================================
   * CHRONOLOGICAL LIST VIEW
   * ==========================================
   */
  function renderListView(filtered) {
    resultsCountEl.textContent = `${filtered.length} release${filtered.length !== 1 ? 's' : ''}`;

    if (filtered.length === 0) {
      agendaContainerEl.style.display = 'none';
      emptyStateEl.style.display = 'block';
      return;
    }

    agendaContainerEl.style.display = 'flex';
    emptyStateEl.style.display = 'none';

    const monthGroups = {};
    filtered.forEach(item => {
      let mKey = 'Undated';
      if (item.date && item.date.length >= 7) {
        mKey = item.date.slice(0, 7);
      }
      if (!monthGroups[mKey]) {
        monthGroups[mKey] = [];
      }
      monthGroups[mKey].push(item);
    });

    const sortedMonthKeys = Object.keys(monthGroups).sort((a, b) => {
      if (a === 'Undated') return 1;
      if (b === 'Undated') return -1;
      return b.localeCompare(a);
    });

    let html = '';

    sortedMonthKeys.forEach(mKey => {
      let monthTitle = 'Date TBA';
      if (mKey !== 'Undated') {
        const [year, month] = mKey.split('-');
        const monthName = MONTHS_EN[parseInt(month, 10) - 1] || month;
        monthTitle = `${monthName} ${year}`;
      }

      const itemsInMonth = monthGroups[mKey];

      const dateGroups = {};
      itemsInMonth.forEach(item => {
        const dKey = item.date || 'Undated';
        if (!dateGroups[dKey]) {
          dateGroups[dKey] = [];
        }
        dateGroups[dKey].push(item);
      });

      const sortedDateKeys = Object.keys(dateGroups).sort((a, b) => {
        if (a === 'Undated') return 1;
        if (b === 'Undated') return -1;
        return b.localeCompare(a);
      });

      html += `
        <section class="month-group">
          <div class="month-heading">
            <span>${monthTitle}</span>
            <span class="month-count">${itemsInMonth.length}</span>
          </div>
      `;

      sortedDateKeys.forEach(dKey => {
        const items = dateGroups[dKey];
        const dateLabel = items[0].formatted_date || dKey;

        html += `
          <div class="date-group">
            <div class="date-heading">${dateLabel}</div>
            <div class="cards-grid">
              ${items.map(renderComicCard).join('')}
            </div>
          </div>
        `;
      });

      html += `</section>`;
    });

    agendaContainerEl.innerHTML = html;

    agendaContainerEl.querySelectorAll('.card-cover img').forEach(img => {
      img.addEventListener('click', (e) => {
        const card = e.target.closest('.comic-card');
        const id = card.dataset.id;
        const item = allReleases.find(r => r.id === id);
        if (item) {
          openReleaseModal(item);
        }
      });
      img.addEventListener('error', function () {
        handleCoverError(this);
      });
    });
  }

  function renderComicCard(item) {
    const isUpcoming = item.status === 'upcoming';
    const statusBadge = isUpcoming
      ? `<span class="badge badge-upcoming">Upcoming</span>`
      : `<span class="badge badge-released">Released</span>`;

    const priceText = item.price
      ? `<span class="card-price">${escapeHtml(item.price)}</span>`
      : `<span class="card-price-unknown">Price TBA</span>`;

    const publisher = item.publisher || item.country_name;
    const coverUrl = item.cover_url || '';

    return `
      <article class="comic-card" data-id="${escapeHtml(item.id)}" data-title="${escapeHtml(item.title)}">
        <div class="card-cover" title="Click to view details and full cover">
          ${coverUrl ? `
            <img src="${escapeHtml(coverUrl)}" 
                 alt="${escapeHtml(item.title)}" 
                 loading="lazy" 
                 data-country="${item.country}"
                 data-title="${escapeHtml(item.title)}">
          ` : `
            <div class="cover-fallback">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
              </svg>
              <span>${escapeHtml(item.country_name)}</span>
            </div>
          `}
        </div>

        <div class="card-body">
          <div class="card-top">
            <div class="card-meta-row">
              <span class="badge badge-country">${escapeHtml(item.country_name)}</span>
              ${statusBadge}
            </div>
            <h3 class="card-title">${escapeHtml(item.title)}</h3>
            <div class="card-publisher">${escapeHtml(publisher)}</div>
          </div>

          <div class="card-bottom">
            ${priceText}
            ${item.url ? `
              <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="card-link">
                View details →
              </a>
            ` : ''}
          </div>
        </div>
      </article>
    `;
  }

  function handleCoverError(imgEl) {
    const parent = imgEl.parentElement;
    const country = imgEl.dataset.country;
    const cObj = availableCountries.find(x => x.code === country);
    const name = cObj ? cObj.name : '';

    parent.innerHTML = `
      <div class="cover-fallback">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
        </svg>
        <span>${escapeHtml(name)}</span>
      </div>
    `;
  }

  /**
   * Modal Lightbox
   */
  function openReleaseModal(item) {
    modalImgEl.src = item.cover_url || '';
    modalImgEl.style.display = item.cover_url ? 'block' : 'none';

    const isUpcoming = item.status === 'upcoming';
    const statusText = isUpcoming ? 'Upcoming' : 'Released';
    const dateFormatted = item.formatted_date || item.date || 'Date TBA';
    const priceText = item.price ? ` • ${escapeHtml(item.price)}` : '';
    const publisherText = item.publisher ? ` • ${escapeHtml(item.publisher)}` : '';

    modalCaptionEl.innerHTML = `
      <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.25rem;">${escapeHtml(item.title)}</div>
      <div style="color: var(--text-muted); font-size: 0.8125rem;">
        ${escapeHtml(item.country_name)} • ${dateFormatted} (${statusText})${publisherText}${priceText}
      </div>
      ${item.url ? `
        <div style="margin-top: 0.75rem;">
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="btn btn-secondary" style="font-size: 0.8125rem;">
            Open official page →
          </a>
        </div>
      ` : ''}
    `;

    modalEl.classList.add('active');
    modalEl.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modalEl.classList.remove('active');
    modalEl.setAttribute('aria-hidden', 'true');
    modalImgEl.src = '';
    document.body.style.overflow = '';
  }

  modalCloseBtn.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', closeModal);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalEl.classList.contains('active')) {
      closeModal();
    }
  });

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Initialize
  initTheme();
  loadData();
})();
