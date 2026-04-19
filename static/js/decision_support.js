(function () {
  var canvas = document.getElementById("chartScatter");
  if (!canvas || typeof Chart === "undefined") return;

  var chart;
  var meta = { mal_labels: [], trait_labels: [], dept_labels: [] };
  var lastPoints = [];

  function $(id) {
    return document.getElementById(id);
  }

  function colorFor(risk) {
    if (risk > 75) return "#fb7185";
    if (risk > 40) return "#eab308";
    return "#10b981";
  }

  function val(p, axis) {
    switch (axis) {
      case "age":
        return p.age;
      case "duree":
        return p.stayDuration;
      case "risque":
        return p.riskScore;
      case "douleur":
        return p.painLevel;
      case "maladie":
        return p.maladieCode;
      case "traitement":
        return p.traitementCode;
      case "service":
        return p.deptCode;
      default:
        return p.age;
    }
  }

  function titleFr(axis) {
    switch (axis) {
      case "age":
        return "Âge (ans)";
      case "duree":
        return "Durée de séjour (jours)";
      case "risque":
        return "Score de risque (%)";
      case "douleur":
        return "Douleur — proxy clinique (1–10)";
      case "maladie":
        return "Maladie (catégorie)";
      case "traitement":
        return "Traitement (catégorie)";
      case "service":
        return "Service (catégorie)";
      default:
        return "";
    }
  }

  function catLabels(axis) {
    if (axis === "maladie") return meta.mal_labels || [];
    if (axis === "traitement") return meta.trait_labels || [];
    if (axis === "service") return meta.dept_labels || [];
    return [];
  }

  function tickCb(axis) {
    return function (val) {
      var labs = catLabels(axis);
      if (labs.length) {
        var i = Math.round(Number(val));
        if (i >= 0 && i < labs.length) return labs[i];
        return "";
      }
      return val;
    };
  }

  function isCat(axis) {
    return axis === "maladie" || axis === "traitement" || axis === "service";
  }

  function numScale(axis) {
    return axis === "age" || axis === "duree" || axis === "risque" || axis === "douleur";
  }

  function scaleRange(axis) {
    if (!isCat(axis)) return {};
    var n = catLabels(axis).length;
    if (n <= 0) return {};
    return { min: -0.5, max: n - 0.5 };
  }

  function rapportsPeriodParam() {
    var el = document.getElementById("rapports-filter-state");
    if (!el) return "all";
    try {
      var o = JSON.parse(el.textContent);
      return o.periode || "all";
    } catch (e) {
      return "all";
    }
  }

  function buildQuery() {
    var dept = $("ds-dept");
    var deptVal = dept && dept.value ? dept.value : "Tous";
    if (deptVal === "") deptVal = "Tous";
    var sex = $("ds-sex");
    var mal = $("ds-maladie");
    var trait = $("ds-traitement");
    var ax = $("ds-axis-x");
    var ay = $("ds-axis-y");
    return (
      "?dept=" +
      encodeURIComponent(deptVal) +
      "&sex=" +
      encodeURIComponent(sex ? sex.value : "Tous") +
      "&maladie=" +
      encodeURIComponent(mal ? mal.value : "Toutes") +
      "&traitement=" +
      encodeURIComponent(trait ? trait.value : "Tous") +
      "&axis_x=" +
      encodeURIComponent(ax ? ax.value : "age") +
      "&axis_y=" +
      encodeURIComponent(ay ? ay.value : "duree") +
      "&periode=" +
      encodeURIComponent(rapportsPeriodParam())
    );
  }

  function renderInsights(htmlList) {
    var ul = $("ds-insights-list");
    if (!ul) return;
    ul.innerHTML = "";
    (htmlList || []).forEach(function (html) {
      var li = document.createElement("li");
      li.className = "relative pl-5 text-sm text-slate-700 leading-relaxed";
      li.innerHTML =
        '<span class="absolute left-0 top-2 w-1.5 h-1.5 rounded-full bg-teal-500"></span><span>' +
        html +
        "</span>";
      ul.appendChild(li);
    });
  }

  function draw(bundle) {
    var pts = bundle.points || [];
    lastPoints = pts;
    meta = bundle.meta || { mal_labels: [], trait_labels: [], dept_labels: [] };
    renderInsights(bundle.insights_html);

    var axEl = $("ds-axis-x");
    var ayEl = $("ds-axis-y");
    var axKey = axEl ? axEl.value : bundle.axis_x || "age";
    var ayKey = ayEl ? ayEl.value : bundle.axis_y || "duree";

    var bubbleRows = pts.map(function (p) {
      return {
        x: val(p, axKey),
        y: val(p, ayKey),
        r: 5 + Math.min(16, (p.painLevel || 5) * 1.55),
      };
    });

    if (chart) chart.destroy();

    var xScale = Object.assign(
      {
        title: { display: true, text: titleFr(axKey), color: "#64748b", font: { size: 12, weight: "500" } },
        ticks: { color: "#94a3b8", callback: tickCb(axKey), maxTicksLimit: isCat(axKey) ? 24 : 14 },
        grid: { color: "#e2e8f0", borderDash: [4, 4], drawBorder: false },
      },
      scaleRange(axKey),
      numScale(axKey) ? { beginAtZero: true } : {}
    );

    var yScale = Object.assign(
      {
        title: { display: true, text: titleFr(ayKey), color: "#64748b", font: { size: 12, weight: "500" } },
        ticks: { color: "#94a3b8", callback: tickCb(ayKey), maxTicksLimit: isCat(ayKey) ? 24 : 12 },
        grid: { color: "#e2e8f0", borderDash: [4, 4], drawBorder: false },
      },
      scaleRange(ayKey),
      numScale(ayKey) ? { beginAtZero: true } : {}
    );

    chart = new Chart(canvas.getContext("2d"), {
      type: "bubble",
      data: {
        datasets: [
          {
            label: "Patients",
            data: bubbleRows,
            parsing: false,
            backgroundColor: pts.map(function (p) {
              return colorFor(p.riskScore) + "88";
            }),
            borderColor: pts.map(function (p) {
              return colorFor(p.riskScore);
            }),
            borderWidth: 1.5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var p = lastPoints[ctx.dataIndex];
                if (!p) return "";
                return [
                  "Âge : " + p.age + " ans · Séjour : " + p.stayDuration + " j",
                  "Risque : " + Math.round(p.riskScore) + "% · Douleur proxy : " + p.painLevel + "/10",
                  (p.dept || "") + " · " + (p.maladie || ""),
                ];
              },
            },
          },
        },
        scales: {
          x: xScale,
          y: yScale,
        },
      },
    });
  }

  function load() {
    fetch("/api/decision-support" + buildQuery())
      .then(function (r) {
        return r.json();
      })
      .then(draw)
      .catch(function () {});
  }

  ["ds-dept", "ds-sex", "ds-maladie", "ds-traitement", "ds-axis-x", "ds-axis-y"].forEach(function (id) {
    var el = $(id);
    if (el) el.addEventListener("change", load);
  });

  load();
})();
