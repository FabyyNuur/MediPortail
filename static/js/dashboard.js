(function () {
  var el = document.getElementById("dashboard-data");
  if (!el || typeof Chart === "undefined") return;
  var data = JSON.parse(el.textContent);
  var colors = data.chart_colors || ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#06B6D4"];

  var aw = data.admissions_week;
  if (aw.labels && aw.labels.length && document.getElementById("chartAdmissions")) {
    new Chart(document.getElementById("chartAdmissions"), {
      type: "line",
      data: {
        labels: aw.labels,
        datasets: [
          {
            label: "Admissions",
            data: aw.values,
            borderColor: colors[0],
            backgroundColor: colors[0] + "22",
            fill: true,
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#94a3b8" } },
          y: { grid: { color: "#f1f5f9" }, ticks: { color: "#94a3b8" } },
        },
      },
    });
  }

  var ag = data.age_groups;
  if (ag.labels && ag.labels.length && document.getElementById("chartAge")) {
    new Chart(document.getElementById("chartAge"), {
      type: "doughnut",
      data: {
        labels: ag.labels,
        datasets: [
          {
            data: ag.values,
            backgroundColor: colors.slice(0, ag.labels.length),
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "60%",
        plugins: { legend: { display: false } },
      },
    });
    var leg = document.getElementById("ageLegend");
    if (leg) {
      ag.labels.forEach(function (lab, i) {
        var d = document.createElement("div");
        d.className = "flex items-center gap-2";
        d.innerHTML =
          '<span class="w-2.5 h-2.5 rounded-full flex-shrink-0" style="background:' +
          colors[i % colors.length] +
          '"></span>' +
          lab;
        leg.appendChild(d);
      });
    }
  }

  var cd = data.cost_by_dept;
  if (cd.labels && cd.labels.length && document.getElementById("chartCostDept")) {
    new Chart(document.getElementById("chartCostDept"), {
      type: "bar",
      data: {
        labels: cd.labels,
        datasets: [
          {
            label: "€",
            data: cd.values,
            backgroundColor: cd.labels.map(function (_, i) {
              return colors[i % colors.length];
            }),
            borderRadius: 4,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: "#f1f5f9" }, ticks: { color: "#64748b" } },
          y: { grid: { display: false }, ticks: { color: "#64748b" } },
        },
      },
    });
  }

  var filterForm = document.getElementById("dashboard-filters");
  if (filterForm) {
    filterForm.addEventListener("change", function () {
      filterForm.submit();
    });
  }
})();
