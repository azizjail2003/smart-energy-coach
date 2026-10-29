"use strict";

// Shared helpers: API requests, chart rendering, loading/retry states, theme, rail, tooltips and status bar.
window.SEM = (function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const styles = getComputedStyle(document.documentElement);
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CATEGORY_COLORS = {
    heating: "--brand",
    lighting: "--chart-lighting",
    servers: "--chart-servers",
    other: "--chart-other",
  };

  function token(name) {
    return styles.getPropertyValue(name).trim();
  }

  function faded(hex) {
    const value = parseInt(hex.slice(1), 16);
    return `rgba(${value >> 16}, ${(value >> 8) & 255}, ${value & 255}, 0.3)`;
  }

  function apiUrl(path, params) {
    const url = new URL(path, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "") {
        url.searchParams.set(key, value);
      }
    });
    return url.toString();
  }

  async function fetchJSON(url, options = {}) {
    const headers = { Accept: "application/json" };
    let body;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = csrfToken;
      body = JSON.stringify(options.body);
    }

    let response;
    try {
      response = await fetch(url, { method: options.method || "GET", headers, body, credentials: "same-origin" });
    } catch (error) {
      throw new Error("The server could not be reached. Check the connection and try again.");
    }

    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }
    if (!response.ok) {
      const message = data && data.error ? data.error.message : `The request failed (HTTP ${response.status}).`;
      throw new Error(message);
    }
    return data;
  }

  function formatValue(value, unit) {
    if (value === null || value === undefined) {
      return "No data";
    }
    return unit === "%" ? `${value}%` : `${value.toFixed(2)} ${unit}`;
  }

  function formatClock(isoString, withSeconds) {
    const options = { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin", hourCycle: "h23" };
    if (withSeconds) {
      options.second = "2-digit";
    }
    return new Intl.DateTimeFormat("en-GB", options).format(new Date(isoString));
  }

  function lineDatasets(chart) {
    const primary = token("--brand");
    const compare = token("--chart-compare");
    const above = new Set(chart.above_limit);
    const datasets = chart.datasets.map((set) => {
      const isPrimary = set.key === "primary";
      const pointColors = set.data.map((_, index) => (isPrimary && above.has(index) ? token("--primary-ink") : isPrimary ? primary : compare));
      return {
        label: set.label,
        data: set.data,
        borderColor: isPrimary ? primary : compare,
        backgroundColor: pointColors,
        pointBorderColor: pointColors,
        borderWidth: 2,
        borderDash: isPrimary ? [] : [5, 4],
        pointRadius: set.data.map((_, index) => (isPrimary && above.has(index) ? 5 : isPrimary ? 2.5 : 2)),
        pointHoverRadius: 6,
        tension: 0.25,
        spanGaps: false,
        order: isPrimary ? 1 : 2,
      };
    });
    if (chart.limit) {
      datasets.push({
        label: chart.limit.label,
        data: chart.labels.map(() => chart.limit.value),
        borderColor: compare,
        backgroundColor: compare,
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
        order: 3,
      });
    }
    return datasets;
  }

  function barDatasets(chart, highlight) {
    let colors = token("--brand");
    if (chart.categories) {
      colors = chart.categories.map((id) => {
        const color = token(CATEGORY_COLORS[id]);
        return highlight && highlight !== id ? faded(color) : color;
      });
    }
    return [{
      label: chart.datasets[0].label,
      data: chart.datasets[0].data,
      backgroundColor: colors,
      borderRadius: 2,
      maxBarThickness: 56,
    }];
  }

  // Draws the value above each bar, like the percentages in the approved design.
  const barValueLabels = {
    id: "barValueLabels",
    afterDatasetsDraw(instance, args, options) {
      const { ctx } = instance;
      const values = instance.data.datasets[0].data;
      ctx.save();
      ctx.font = `600 12px ${token("--font")}`;
      ctx.fillStyle = token("--text");
      ctx.textAlign = "center";
      instance.getDatasetMeta(0).data.forEach((bar, index) => {
        ctx.fillText(options.format(values[index]), bar.x, bar.y - 6);
      });
      ctx.restore();
    },
  };

  function chartConfig(chart, highlight) {
    const muted = token("--muted");
    const grid = token("--chart-grid");
    const isLine = chart.type === "line";
    const narrow = window.matchMedia("(max-width: 520px)").matches;
    const above = new Set(chart.above_limit);
    const config = {
      type: chart.type,
      data: { labels: chart.labels, datasets: isLine ? lineDatasets(chart) : barDatasets(chart, highlight) },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: reduceMotion ? false : { duration: 250 },
        interaction: { mode: "index", intersect: false },
        layout: { padding: { top: isLine ? 4 : 20 } },
        plugins: {
          legend: {
            display: isLine,
            position: "bottom",
            align: "start",
            labels: { usePointStyle: true, pointStyle: "line", boxWidth: 28, color: token("--text"), padding: 16 },
          },
          tooltip: {
            callbacks: {
              label(context) {
                let text = `${context.dataset.label}: ${formatValue(context.parsed.y, chart.unit)}`;
                if (isLine && context.datasetIndex === 0 && above.has(context.dataIndex)) {
                  text += " (above limit)";
                }
                return text;
              },
            },
          },
          barValueLabels: { format: (value) => (chart.unit === "%" ? `${value}%` : value.toFixed(1)) },
        },
        scales: {
          x: {
            title: { display: true, text: chart.x_title, color: muted },
            grid: { color: grid, drawTicks: false },
            ticks: { color: muted, maxRotation: 0, autoSkip: true, maxTicksLimit: isLine ? (narrow ? 5 : 9) : 16, padding: 6 },
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: chart.y_title, color: muted },
            grid: { color: grid, drawTicks: false },
            border: { display: false },
            ticks: { color: muted, padding: 6, callback: (value) => (chart.unit === "%" ? `${value}%` : value) },
          },
        },
      },
    };
    if (!isLine) {
      config.plugins = [barValueLabels];
    }
    return config;
  }

  function renderTable(target, chart) {
    const table = document.createElement("table");
    const head = table.createTHead().insertRow();
    [chart.x_title, ...chart.datasets.map((set) => `${set.label} (${chart.unit})`)].forEach((text) => {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = text;
      head.appendChild(cell);
    });
    const body = table.createTBody();
    chart.labels.forEach((label, index) => {
      const row = body.insertRow();
      const header = document.createElement("th");
      header.scope = "row";
      header.textContent = label;
      row.appendChild(header);
      chart.datasets.forEach((set) => {
        const value = set.data[index];
        row.insertCell().textContent = value === null ? "No data" : String(value);
      });
    });
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.appendChild(table);
    target.replaceChildren(wrap);
  }

  // Charts drawn on this page, kept so they can be redrawn in the new colours when the theme changes.
  const drawnCharts = new Map();

  function renderChart(container, chart, options = {}) {
    const canvas = container.querySelector("canvas");
    if (container.chartInstance) {
      container.chartInstance.destroy();
    }
    Chart.defaults.font.family = token("--font");
    Chart.defaults.font.size = 12;
    Chart.defaults.color = token("--muted");
    container.chartInstance = new Chart(canvas, chartConfig(chart, options.highlight));
    drawnCharts.set(container, { chart, options });
    canvas.setAttribute("aria-label", chart.summary);
    container.querySelector("[data-summary]").textContent = chart.summary;
    renderTable(container.querySelector("[data-table]"), chart);
  }

  function redrawCharts() {
    drawnCharts.forEach(({ chart, options }, container) => renderChart(container, chart, options));
  }

  // Shows a loading placeholder, runs `load`, and replaces the placeholder with a retry option on failure.
  function loadInto(container, load) {
    const state = container.querySelector("[data-state]");
    const run = async () => {
      state.hidden = false;
      state.textContent = "Loading chart…";
      container.setAttribute("aria-busy", "true");
      try {
        await load();
        state.hidden = true;
      } catch (error) {
        const message = document.createElement("p");
        message.textContent = `Could not load the chart. ${error.message}`;
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "button button--secondary";
        retry.textContent = "Retry";
        retry.addEventListener("click", run);
        state.replaceChildren(message, retry);
      } finally {
        container.removeAttribute("aria-busy");
      }
    };
    run();
  }

  // Shell preferences are stored in the browser only; the page works the same without them.

  function savePreference(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      // Private windows can refuse storage; the choice then lasts until the page is left.
    }
  }

  const root = document.documentElement;
  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const THEMES = ["auto", "dark", "light"];
  const THEME_NAMES = { auto: "System", dark: "Dark", light: "Light" };

  function applyTheme(preference) {
    const dark = preference === "dark" || (preference === "auto" && darkQuery.matches);
    const changed = root.dataset.theme !== (dark ? "dark" : "light");
    root.dataset.themePref = preference;
    root.dataset.theme = dark ? "dark" : "light";
    const next = THEMES[(THEMES.indexOf(preference) + 1) % THEMES.length];
    const button = document.querySelector("[data-theme-toggle]");
    const label = `Theme: ${THEME_NAMES[preference]}`;
    button.querySelector("[data-theme-label]").textContent = label;
    button.dataset.tip = `${label}. Switch to ${THEME_NAMES[next].toLowerCase()}`;
    button.setAttribute("aria-label", button.dataset.tip);
    if (changed) {
      redrawCharts();
    }
  }

  function setupTheme() {
    applyTheme(root.dataset.themePref || "auto");
    document.querySelector("[data-theme-toggle]").addEventListener("click", () => {
      const current = root.dataset.themePref || "auto";
      const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
      savePreference("sem-theme", next);
      applyTheme(next);
    });
    darkQuery.addEventListener("change", () => applyTheme(root.dataset.themePref || "auto"));
  }

  function setupRail() {
    const toggle = document.querySelector("[data-rail-toggle]");
    const label = toggle.querySelector("[data-rail-toggle-label]");
    const show = (on) => {
      root.dataset.railHover = on ? "on" : "off";
      toggle.setAttribute("aria-pressed", String(on));
      label.textContent = `Expand on hover: ${on ? "on" : "off"}`;
      toggle.dataset.tip = on ? "Keep the menu narrow" : "Expand the menu on hover";
    };
    show(root.dataset.railHover !== "off");
    toggle.addEventListener("click", () => {
      const on = root.dataset.railHover === "off";
      savePreference("sem-rail-hover", on ? "on" : "off");
      show(on);
    });
  }

  // One fast tooltip for every control with data-tip. Rail entries only need it while the rail
  // stays narrow, because the expanded rail already shows their labels.
  function setupTooltips() {
    const tip = document.createElement("div");
    tip.className = "tooltip";
    tip.setAttribute("aria-hidden", "true");
    document.body.appendChild(tip);
    const narrowScreen = window.matchMedia("(max-width: 760px)");
    let timer = null;

    function hide() {
      window.clearTimeout(timer);
      tip.classList.remove("is-visible");
    }

    function show(target) {
      if (narrowScreen.matches || ("tipRail" in target.dataset && root.dataset.railHover !== "off")) {
        return;
      }
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        tip.textContent = target.dataset.tip;
        const box = target.getBoundingClientRect();
        const inRail = target.closest("[data-rail]") !== null;
        const left = inRail ? box.right + 12 : box.left + box.width / 2 - tip.offsetWidth / 2;
        const top = inRail ? box.top + box.height / 2 - tip.offsetHeight / 2 : box.bottom + 8;
        tip.style.left = `${Math.max(8, Math.min(left, window.innerWidth - tip.offsetWidth - 8))}px`;
        tip.style.top = `${Math.max(8, top)}px`;
        tip.classList.add("is-visible");
      }, 80);
    }

    document.querySelectorAll("[data-tip]").forEach((target) => {
      target.addEventListener("mouseenter", () => show(target));
      target.addEventListener("mouseleave", hide);
      target.addEventListener("focus", () => {
        if (target.matches(":focus-visible")) {
          show(target);
        }
      });
      target.addEventListener("blur", hide);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hide();
      }
    });
    window.addEventListener("scroll", hide, true);
  }

  // The left end of the status bar: live state for pages that poll, "Demo data" otherwise.
  function setStatus(state, text) {
    const dot = document.querySelector("[data-status-dot]");
    dot.className = `dot dot--${state}`;
    document.querySelector("[data-status-text]").textContent = text;
  }

  function setupLayout() {
    document.querySelectorAll("[data-auto-submit] select").forEach((select) => {
      select.addEventListener("change", () => select.form.submit());
    });
    setupTheme();
    setupRail();
    setupTooltips();
  }

  setupLayout();

  return { apiUrl, fetchJSON, formatClock, renderChart, loadInto, setStatus };
})();
