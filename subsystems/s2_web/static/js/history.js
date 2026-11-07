"use strict";

(function () {
  const { apiUrl, fetchJSON, renderChart, loadInto } = window.SEM;
  const root = document.querySelector("[data-history]");
  const { building, period, day, category } = root.dataset;
  const container = root.querySelector('[data-chart="history-chart"]');

  loadInto(container, async () => {
    if (period === "today") {
      const data = await fetchJSON(apiUrl("/api/hourly", { building, day, category }));
      renderChart(container, data.chart);
    } else {
      const data = await fetchJSON(apiUrl("/api/aggregates", { building, period }));
      renderChart(container, data.daily_chart);
    }
  });
})();
