"use strict";

(function () {
  const { apiUrl, fetchJSON, renderChart, loadInto, setStatus } = window.SEM;
  const root = document.querySelector("[data-dashboard]");
  const building = root.dataset.building;
  const day = root.dataset.day;
  let category = root.dataset.category;

  const hourlyChart = root.querySelector('[data-chart="hourly-chart"]');
  const deviceChart = root.querySelector('[data-chart="device-chart"]');
  const compareBox = root.querySelector("[data-compare]");
  let deviceData = null;

  function loadHourly() {
    loadInto(hourlyChart, async () => {
      const data = await fetchJSON(apiUrl("/api/hourly", {
        building, day, category, compare: compareBox.checked ? 1 : 0,
      }));
      renderChart(hourlyChart, data.chart);
    });
  }

  function loadDevices() {
    loadInto(deviceChart, async () => {
      const data = await fetchJSON(apiUrl("/api/aggregates", { building, period: "week" }));
      deviceData = data.chart;
      root.querySelector("[data-week-total]").textContent = `${data.total_kwh.toFixed(1)} kWh`;
      renderChart(deviceChart, deviceData, { highlight: category });
    });
  }

  // KPI cards

  function setTrend(card, metric) {
    const trend = card.querySelector("[data-trend]");
    trend.classList.remove("trend--down", "trend--up", "trend--flat", "trend--good", "trend--bad");
    trend.classList.add(`trend--${metric.trend}`, metric.trend === "up" ? "trend--bad" : "trend--good");
    trend.querySelector("[data-trend-word]").textContent = { down: "Down", up: "Up" }[metric.trend] || "No change";
    trend.querySelector("[data-trend-text]").textContent = metric.change_display;
  }

  function setSpark(card, spark) {
    card.querySelector("[data-spark-svg]").setAttribute("aria-label", spark.label);
    card.querySelector("[data-spark-area]").setAttribute("d", spark.area);
    card.querySelector("[data-spark-line]").setAttribute("d", spark.line);
    const dot = card.querySelector("[data-spark-dot]");
    dot.style.left = `${spark.end_x}%`;
    dot.style.top = `${spark.end_y}%`;
  }

  function showKpis(kpis) {
    Object.entries(kpis).forEach(([name, metric]) => {
      const card = root.querySelector(`[data-kpi="${name}"]`);
      card.querySelector("[data-value]").textContent = metric.display;
      setTrend(card, metric);
      if (metric.spark) {
        setSpark(card, metric.spark);
      }
    });
    root.querySelector("[data-savings-co2]").textContent = kpis.savings.co2_display;
    root.querySelector("[data-savings-today]").classList.toggle("is-negative", kpis.savings.negative);
    const week = root.querySelector("[data-savings-week]");
    week.querySelector("[data-week-eur]").textContent = kpis.savings.week.display;
    week.querySelector("[data-week-co2]").textContent = kpis.savings.week.co2_display;
    week.classList.toggle("is-negative", kpis.savings.week.negative);
    root.querySelector("[data-savings-scope]").hidden = !category;
  }

  async function loadKpis() {
    const error = root.querySelector("[data-kpis-error]");
    error.hidden = true;
    try {
      const data = await fetchJSON(apiUrl("/api/kpis", { building, category }));
      showKpis(data.kpis);
    } catch (problem) {
      // Never leave the previous category's figures under the new selection.
      root.querySelectorAll("[data-kpi] [data-value]").forEach((value) => { value.textContent = "–"; });
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "button button--secondary";
      retry.textContent = "Retry";
      retry.addEventListener("click", loadKpis);
      const message = document.createElement("span");
      message.textContent = `Could not load the figures. ${problem.message}`;
      error.replaceChildren(message, retry);
      error.hidden = false;
    }
  }

  root.querySelectorAll("[data-category-chip]").forEach((chip) => {
    chip.addEventListener("click", (event) => {
      event.preventDefault();
      if (chip.dataset.categoryChip === category) {
        return;
      }
      category = chip.dataset.categoryChip;
      root.querySelectorAll("[data-category-chip]").forEach((other) => {
        const selected = other === chip;
        other.classList.toggle("is-selected", selected);
        if (selected) {
          other.setAttribute("aria-current", "true");
        } else {
          other.removeAttribute("aria-current");
        }
      });
      window.history.replaceState(null, "", chip.href);
      loadKpis();
      loadHourly();
      if (deviceData) {
        renderChart(deviceChart, deviceData, { highlight: category });
      }
    });
  });

  compareBox.addEventListener("change", loadHourly);

  // Live score: every 10 s while the page is visible, never two requests at once.

  const score = root.querySelector("[data-score]");
  const scoreValue = score.querySelector("[data-score-value]");
  const scoreTime = score.querySelector("[data-score-time]");
  const scoreError = score.querySelector("[data-score-error]");
  const gauge = score.querySelector("[data-gauge]");
  const gaugeNeedle = score.querySelector("[data-gauge-needle]");
  const scoreBand = score.querySelector("[data-score-band]");
  let timer = null;
  let inFlight = false;

  async function pollScore() {
    if (inFlight) {
      return;
    }
    inFlight = true;
    try {
      const data = await fetchJSON(apiUrl("/api/score", { building }));
      scoreValue.textContent = data.display;
      gauge.className = `gauge gauge--${data.band.band}`;
      gaugeNeedle.style.transform = `rotate(${data.band.needle_deg}deg)`;
      scoreBand.textContent = data.band.label;
      scoreTime.textContent = data.time_display;
      scoreTime.dateTime = data.measured_at;
      scoreError.hidden = true;
      setStatus("live", `Live · score updated ${data.time_display}`);
    } catch (problem) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.textContent = "Retry now";
      retry.addEventListener("click", pollScore);
      scoreError.replaceChildren(`Live update failed. ${problem.message}`, retry);
      scoreError.hidden = false;
      setStatus("failed", "Live update failed");
    } finally {
      inFlight = false;
    }
  }

  function startPolling() {
    if (timer === null) {
      timer = window.setInterval(refresh, 10000);
    }
  }

  function stopPolling() {
    window.clearInterval(timer);
    timer = null;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopPolling();
      setStatus("demo", "Live updates paused");
    } else {
      refresh();
      startPolling();
    }
  });

  // Alert banner: refreshed with the score, so a new alert shows within one 10 s cycle.
  // Dismissing hides the alerts seen so far; a different set of alerts shows the banner again.

  const banner = root.querySelector("[data-banner]");
  let dismissedKey = null;

  function showBanner(data) {
    const key = data ? data.key : "";
    banner.dataset.bannerKey = key;
    if (!data || key === dismissedKey) {
      banner.hidden = true;
      return;
    }
    banner.querySelector("[data-banner-title]").textContent = data.title;
    banner.querySelector("[data-banner-text]").textContent = data.text;
    banner.querySelector("[data-banner-list]").replaceChildren(...data.lines.map((text) => {
      const line = document.createElement("li");
      line.textContent = text;
      return line;
    }));
    banner.hidden = false;
  }

  async function pollAlerts() {
    try {
      const data = await fetchJSON(apiUrl("/api/alerts", { building }));
      showBanner(data.banner);
    } catch (problem) {
      // Keep the last banner; the score area already reports a failed refresh.
    }
  }

  banner.querySelector("[data-banner-close]").addEventListener("click", () => {
    dismissedKey = banner.dataset.bannerKey;
    banner.hidden = true;
    document.getElementById("main").focus();
  });

  function refresh() {
    pollScore();
    pollAlerts();
  }

  loadHourly();
  loadDevices();
  if (!document.hidden) {
    setStatus("live", "Live · first score update in 10 s");
    startPolling();
  }
})();
