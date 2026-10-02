/* PrepAI analytics charts (Chart.js). Colours come from CSS tokens so light/dark
   each use their own validated steps; charts rebuild when the theme changes. */
(function () {
  "use strict";

  const charts = [];

  function tokens() {
    const dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
    // brand: single-series marks. series1/2: validated categorical pair for multi-series.
    return dark
      ? { brand: "#5eead4", series1: "#3987e5", series2: "#d95926", neutral: "#4b5e5c", surface: "#111d1c", text: "#b2c4c2", muted: "#7f9391", grid: "#223533", axis: "#2f4745" }
      : { brand: "#0f766e", series1: "#2a78d6", series2: "#eb6834", neutral: "#c3d0cf", surface: "#ffffff", text: "#3f4e4d", muted: "#62706e", grid: "#e6eeed", axis: "#c3d0cf" };
  }

  function read(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function baseOptions(t, { percent = true, legend = false } = {}) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: legend, position: "top", align: "start", labels: { color: t.text, boxWidth: 12, boxHeight: 12, useBorderRadius: true, borderRadius: 3 } },
        tooltip: {
          backgroundColor: t.surface, titleColor: t.text, bodyColor: t.text, borderColor: t.grid, borderWidth: 1,
          padding: 10, cornerRadius: 8, boxPadding: 4,
          callbacks: percent ? { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y ?? ctx.parsed.x}%` } : {},
        },
      },
      scales: {
        x: { grid: { display: false }, border: { color: t.axis }, ticks: { color: t.muted, maxRotation: 0, autoSkip: true } },
        y: {
          beginAtZero: true, max: percent ? 100 : undefined,
          grid: { color: t.grid }, border: { display: false },
          ticks: { color: t.muted, callback: percent ? (v) => `${v}%` : undefined, maxTicksLimit: 6 },
        },
      },
    };
  }

  function build() {
    if (!window.Chart) return;
    charts.splice(0).forEach((c) => c.destroy());
    const t = tokens();
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

    // Subject-wise accuracy — single series, no legend (the title names it).
    const subjects = read("subject-data");
    const subjectCanvas = document.getElementById("subjectChart");
    if (subjects && subjects.length && subjectCanvas) {
      charts.push(new Chart(subjectCanvas, {
        type: "bar",
        data: {
          labels: subjects.map((s) => s.label),
          datasets: [{ label: "Accuracy", data: subjects.map((s) => s.accuracy), backgroundColor: t.brand,
            borderRadius: 4, borderSkipped: "start", maxBarThickness: 32 }],
        },
        options: baseOptions(t),
      }));
    }

    // Score trend — single line, crosshair tooltip.
    const trend = read("trend-data");
    const trendCanvas = document.getElementById("trendChart");
    if (trend && trend.length && trendCanvas) {
      const opts = baseOptions(t);
      opts.plugins.tooltip.callbacks.title = (items) => `${trend[items[0].dataIndex].title} · ${items[0].label}`;
      charts.push(new Chart(trendCanvas, {
        type: "line",
        data: {
          labels: trend.map((p) => p.date),
          datasets: [{ label: "Score", data: trend.map((p) => p.percentage), borderColor: t.brand, backgroundColor: t.brand,
            borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, pointBorderColor: t.surface, pointBorderWidth: 2, tension: 0.25 }],
        },
        options: opts,
      }));
    }

    // Test-type breakdown — stacked counts with a 2px surface gap between segments.
    const types = read("testtype-data");
    const typeCanvas = document.getElementById("testTypeChart");
    if (types && types.length && typeCanvas) {
      const opts = baseOptions(t, { percent: false, legend: true });
      opts.scales.x.stacked = true;
      opts.scales.y.stacked = true;
      const seg = (label, key, color) => ({ label, data: types.map((r) => r[key]), backgroundColor: color,
        borderColor: t.surface, borderWidth: 2, borderRadius: 4, borderSkipped: false, maxBarThickness: 36 });
      charts.push(new Chart(typeCanvas, {
        type: "bar",
        data: {
          labels: types.map((r) => r.label),
          datasets: [seg("Correct", "correct", t.series1), seg("Incorrect", "incorrect", t.series2), seg("Skipped", "skipped", t.neutral)],
        },
        options: opts,
      }));
    }
  }

  document.addEventListener("DOMContentLoaded", build);
  document.addEventListener("prepai:themechange", () => setTimeout(build, 0));
})();
