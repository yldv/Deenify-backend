(function () {
  function readChartData() {
    var el = document.getElementById("deenify-chart-data");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function makeChart(canvasId, config) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return;
    var existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    new Chart(canvas, config);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var data = readChartData();
    if (!data) return;

    var palette = ["#2ecc71", "#3498db", "#f39c12", "#e74c3c", "#9b59b6", "#1abc9c"];
    var gridColor = "rgba(0,0,0,0.06)";

    if (data.answers) {
      makeChart("chartAnswers", {
        type: "line",
        data: {
          labels: data.answers.labels,
          datasets: [{
            label: data.answers.label,
            data: data.answers.data,
            borderColor: "#3498db",
            backgroundColor: "rgba(52, 152, 219, 0.15)",
            fill: true,
            tension: 0.35,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true } },
          scales: { y: { beginAtZero: true, grid: { color: gridColor } } },
        },
      });
    }

    if (data.users) {
      makeChart("chartUsers", {
        type: "bar",
        data: {
          labels: data.users.labels,
          datasets: [{
            label: data.users.label,
            data: data.users.data,
            backgroundColor: "rgba(46, 204, 113, 0.75)",
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true } },
          scales: { y: { beginAtZero: true, grid: { color: gridColor } } },
        },
      });
    }

    if (data.levels) {
      makeChart("chartLevels", {
        type: "doughnut",
        data: {
          labels: data.levels.labels,
          datasets: [{
            data: data.levels.data,
            backgroundColor: ["#2ecc71", "#f39c12", "#e74c3c"],
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
        },
      });
    }

    if (data.orders) {
      makeChart("chartOrders", {
        type: "pie",
        data: {
          labels: data.orders.labels,
          datasets: [{
            data: data.orders.data,
            backgroundColor: palette,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
        },
      });
    }
  });
})();
