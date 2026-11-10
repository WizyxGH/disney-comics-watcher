/**
 * Disney Comics Agenda — Minimalist Web App
 * Ultra-fast, zero-dependency client logic.
 */

(function () {
  'use strict';

  // State
  let allReleases = [];
  let availableCountries = [];
  let activeCountry = 'all';
  let activeStatus = 'all'; // 'all', 'upcoming', 'released'
  let searchQuery = '';

  // DOM Elements
  const countryChipsEl = document.getElementById('country-chips');
  const activeCountryLabelEl = document.getElementById('active-country-label');
  const agendaContainerEl = document.getElementById('agenda-container');
  const emptyStateEl = document.getElementById('empty-state');
  const resultsCountEl = document.getElementById('results-count');
  const releasesCountBadgeEl = document.getElementById('releases-count-badge');
  const searchInputEl = document.getElementById('search-input');
  const clearSearchBtn = document.getElementById('clear-search');
  const resetFiltersBtn = document.getElementById('reset-filters-btn');
  const lastUpdateEl = document.getElementById('last-update');
  const themeToggleBtn = document.getElementById('theme-toggle');

  // Modal Elements
  const modalEl = document.getElementById('cover-modal');
  const modalImgEl = document.getElementById('modal-image');
  const modalCaptionEl = document.getElementById('modal-caption');
  const modalCloseBtn = modalEl.querySelector('.modal-close');
  const modalBackdrop = modalEl.querySelector('.modal-backdrop');

  // Month names for grouping
  const MONTHS_FR = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
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
        // currently on system preference
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
      releasesCountBadgeEl.textContent = `${allReleases.length} sorties`;
      if (data.generated_at) {
        const dt = new Date(data.generated_at);
        lastUpdateEl.textContent = `Mise à jour : ${dt.toLocaleDateString('fr-FR', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        })}`;
      }

      // Check URL query parameters for default country
      const urlParams = new URLSearchParams(window.location.search);
      const urlCountry = urlParams.get('country');
      if (urlCountry && availableCountries.some(c => c.code.toLowerCase() === urlCountry.toLowerCase())) {
        activeCountry = urlCountry.toLowerCase();
      }

      renderCountryFilters();
      renderAgenda();
    } catch (err) {
      console.error('Failed to load releases data:', err);
      agendaContainerEl.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">⚠️</span>
          <h3>Impossible de charger les données</h3>
          <p>${err.message}</p>
        </div>
      `;
    }
  }

  /**
   * Render Country Filter Pills
   */
  function renderCountryFilters() {
    countryChipsEl.innerHTML = '';

    // "All" pill
    const allChip = document.createElement('button');
    allChip.className = `chip ${activeCountry === 'all' ? 'active' : ''}`;
    allChip.setAttribute('role', 'radio');
    allChip.setAttribute('aria-checked', activeCountry === 'all');
    allChip.innerHTML = `🌐 Tous <span class="chip-count">${allReleases.length}</span>`;
    allChip.addEventListener('click', () => setCountry('all'));
    countryChipsEl.appendChild(allChip);

    // Country pills
    availableCountries.forEach(country => {
      const chip = document.createElement('button');
      chip.className = `chip ${activeCountry === country.code ? 'active' : ''}`;
      chip.setAttribute('role', 'radio');
      chip.setAttribute('aria-checked', activeCountry === country.code);
      chip.innerHTML = `${country.flag} ${country.name} <span class="chip-count">${country.count}</span>`;
      chip.addEventListener('click', () => setCountry(country.code));
      countryChipsEl.appendChild(chip);
    });

    updateActiveCountryLabel();
  }

  function setCountry(code) {
    activeCountry = code;
    // Update URL parameter without reload
    const url = new URL(window.location);
    if (code === 'all') {
      url.searchParams.delete('country');
    } else {
      url.searchParams.set('country', code);
    }
    window.history.replaceState({}, '', url);

    renderCountryFilters();
    renderAgenda();
  }

  function updateActiveCountryLabel() {
    if (activeCountry === 'all') {
      activeCountryLabelEl.textContent = 'Tous les pays';
    } else {
      const c = availableCountries.find(x => x.code === activeCountry);
      activeCountryLabelEl.textContent = c ? `${c.flag} ${c.name}` : activeCountry.toUpperCase();
    }
  }

  /**
   * Status Filter Tabs & Search Event Handlers
   */
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      activeStatus = btn.dataset.status;
      renderAgenda();
    });
  });

  searchInputEl.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    clearSearchBtn.style.display = searchQuery ? 'block' : 'none';
    renderAgenda();
  });

  clearSearchBtn.addEventListener('click', () => {
    searchInputEl.value = '';
    searchQuery = '';
    clearSearchBtn.style.display = 'none';
    renderAgenda();
    searchInputEl.focus();
  });

  resetFiltersBtn.addEventListener('click', () => {
    activeCountry = 'all';
    activeStatus = 'all';
    searchQuery = '';
    searchInputEl.value = '';
    clearSearchBtn.style.display = 'none';

    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.status === 'all');
      b.setAttribute('aria-selected', b.dataset.status === 'all');
    });

    const url = new URL(window.location);
    url.searchParams.delete('country');
    window.history.replaceState({}, '', url);

    renderCountryFilters();
    renderAgenda();
  });

  /**
   * Filter and Group releases
   */
  function getFilteredReleases() {
    return allReleases.filter(release => {
      // Country Filter
      if (activeCountry !== 'all' && release.country !== activeCountry) {
        return false;
      }
      // Status Filter
      if (activeStatus !== 'all' && release.status !== activeStatus) {
        return false;
      }
      // Text Search
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

  /**
   * Render Agenda Timeline
   */
  function renderAgenda() {
    const filtered = getFilteredReleases();
    resultsCountEl.textContent = `${filtered.length} sortie${filtered.length > 1 ? 's' : ''}`;

    if (filtered.length === 0) {
      agendaContainerEl.style.display = 'none';
      emptyStateEl.style.display = 'block';
      return;
    }

    agendaContainerEl.style.display = 'flex';
    emptyStateEl.style.display = 'none';

    // Grouping by Month Key (e.g., "2027-02" or "sans-date")
    const monthGroups = {};
    filtered.forEach(item => {
      let mKey = 'Sans date';
      if (item.date && item.date.length >= 7) {
        mKey = item.date.slice(0, 7); // "YYYY-MM"
      }
      if (!monthGroups[mKey]) {
        monthGroups[mKey] = [];
      }
      monthGroups[mKey].push(item);
    });

    // Sort month keys descending (future -> recent)
    const sortedMonthKeys = Object.keys(monthGroups).sort((a, b) => {
      if (a === 'Sans date') return 1;
      if (b === 'Sans date') return -1;
      return b.localeCompare(a);
    });

    let html = '';

    sortedMonthKeys.forEach(mKey => {
      let monthTitle = 'Date à préciser';
      if (mKey !== 'Sans date') {
        const [year, month] = mKey.split('-');
        const monthName = MONTHS_FR[parseInt(month, 10) - 1] || month;
        monthTitle = `${monthName} ${year}`;
      }

      const itemsInMonth = monthGroups[mKey];

      // Subgroup by exact date
      const dateGroups = {};
      itemsInMonth.forEach(item => {
        const dKey = item.date || 'Non daté';
        if (!dateGroups[dKey]) {
          dateGroups[dKey] = [];
        }
        dateGroups[dKey].push(item);
      });

      const sortedDateKeys = Object.keys(dateGroups).sort((a, b) => {
        if (a === 'Non daté') return 1;
        if (b === 'Non daté') return -1;
        return b.localeCompare(a);
      });

      html += `
        <section class="month-group">
          <div class="month-heading">
            <span>📅 ${monthTitle}</span>
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

    // Attach event listeners for covers (lightbox) and error handling
    agendaContainerEl.querySelectorAll('.card-cover img').forEach(img => {
      img.addEventListener('click', (e) => {
        const card = e.target.closest('.comic-card');
        const title = card.dataset.title;
        openModal(e.target.src, title);
      });
      img.addEventListener('error', function () {
        handleCoverError(this);
      });
    });
  }

  /**
   * Render Single Comic Card
   */
  function renderComicCard(item) {
    const isUpcoming = item.status === 'upcoming';
    const statusBadge = isUpcoming
      ? `<span class="badge badge-upcoming">À paraître</span>`
      : `<span class="badge badge-released">Disponible</span>`;

    const priceText = item.price
      ? `<span class="card-price">${escapeHtml(item.price)}</span>`
      : `<span class="card-price-unknown">Prix non communiqué</span>`;

    const publisher = item.publisher || item.country_name;
    const coverUrl = item.cover_url || '';

    return `
      <article class="comic-card" data-title="${escapeHtml(item.title)}">
        <div class="card-cover" title="Cliquer pour agrandir la couverture">
          ${coverUrl ? `
            <img src="${escapeHtml(coverUrl)}" 
                 alt="${escapeHtml(item.title)}" 
                 loading="lazy" 
                 data-country="${item.country}"
                 data-title="${escapeHtml(item.title)}">
          ` : `
            <div class="cover-fallback">
              <span class="fallback-flag">${item.country_flag}</span>
              <span>${escapeHtml(item.country_name)}</span>
            </div>
          `}
        </div>

        <div class="card-body">
          <div class="card-top">
            <div class="card-meta-row">
              <span class="badge badge-country">${item.country_flag} ${escapeHtml(item.country_name)}</span>
              ${statusBadge}
            </div>
            <h3 class="card-title">${escapeHtml(item.title)}</h3>
            <div class="card-publisher">${escapeHtml(publisher)}</div>
          </div>

          <div class="card-bottom">
            ${priceText}
            ${item.url ? `
              <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="card-link">
                Voir détails →
              </a>
            ` : ''}
          </div>
        </div>
      </article>
    `;
  }

  /**
   * Fallback for broken cover URLs
   */
  function handleCoverError(imgEl) {
    const parent = imgEl.parentElement;
    const country = imgEl.dataset.country;
    const cObj = availableCountries.find(x => x.code === country);
    const flag = cObj ? cObj.flag : '📚';
    const name = cObj ? cObj.name : '';

    parent.innerHTML = `
      <div class="cover-fallback">
        <span class="fallback-flag">${flag}</span>
        <span>${escapeHtml(name)}</span>
      </div>
    `;
  }

  /**
   * Modal Lightbox
   */
  function openModal(imgSrc, caption) {
    modalImgEl.src = imgSrc;
    modalCaptionEl.textContent = caption;
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

  /**
   * Utilities
   */
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
