(function () {
  if (typeof Chart === "undefined") return;
  var el = document.getElementById("rapports-data");
  if (!el) return;
  var D = JSON.parse(el.textContent);
  var c = D.chart_colors || ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#06B6D4"];

  function monthlyAS() {
    var m = D.monthly_as;
    if (!m.labels || !m.labels.length || !document.getElementById("chartMonthlyAS")) return;
    new Chart(document.getElementById("chartMonthlyAS"), {
      type: "line",
      data: {
        labels: m.labels,
        datasets: [
          {
            label: "Admissions",
            data: m.admissions,
            borderColor: c[0],
            backgroundColor: c[0] + "22",
            fill: true,
            tension: 0.35,
          },
          {
            label: "Sorties",
            data: m.sorties,
            borderColor: c[1],
            backgroundColor: c[1] + "18",
            fill: true,
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: {
          x: { ticks: { color: "#94a3b8" }, grid: { display: false } },
          y: { ticks: { color: "#94a3b8" }, grid: { color: "#f1f5f9" } },
        },
      },
    });
  }

  function patho() {
    var p = D.patho;
    if (!p.labels || !p.labels.length) return;
    new Chart(document.getElementById("chartPatho"), {
      type: "bar",
      data: {
        labels: p.labels,
        datasets: [
          {
            label: "Cas",
            data: p.values,
            backgroundColor: p.labels.map(function (_, i) {
              return c[i % c.length];
            }),
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
  }

  function stay(id) {
    var p = D.avg_stay;
    if (!p.labels || !p.labels.length) return;
    new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: p.labels,
        datasets: [
          {
            label: "Jours",
            data: p.values,
            backgroundColor: p.labels.map(function (_, i) {
              return c[i % c.length];
            }),
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
  }

  function costs() {
    var m = D.monthly_costs;
    if (!m.labels || !m.labels.length) return;
    new Chart(document.getElementById("chartCosts"), {
      type: "line",
      data: {
        labels: m.labels,
        datasets: [
          {
            label: "€",
            data: m.values,
            borderColor: "#F59E0B",
            backgroundColor: "#F59E0B22",
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
          y: {
            ticks: {
              callback: function (v) {
                return (v / 1000).toFixed(0) + "k€";
              },
            },
          },
        },
      },
    });
  }

  function costBar() {
    var cd = D.cost_by_dept;
    if (!cd.labels || !cd.labels.length) return;
    new Chart(document.getElementById("chartCostBar"), {
      type: "bar",
      data: {
        labels: cd.labels,
        datasets: [
          {
            data: cd.values,
            backgroundColor: cd.labels.map(function (_, i) {
              return c[i % c.length];
            }),
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
  }

  function demoAge() {
    var ag = D.age_groups;
    if (!ag.labels || !document.getElementById("chartDemoAge")) return;
    new Chart(document.getElementById("chartDemoAge"), {
      type: "doughnut",
      data: {
        labels: ag.labels,
        datasets: [{ data: ag.values, backgroundColor: c.slice(0, 4), borderWidth: 0 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: { legend: { display: false } },
      },
    });
  }

  function gender() {
    var g = D.gender;
    if (!g.labels || !g.labels.length) return;
    new Chart(document.getElementById("chartGender"), {
      type: "doughnut",
      data: {
        labels: g.labels,
        datasets: [{ data: g.values, backgroundColor: [c[0], "#EC4899"], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: "55%" },
    });
  }

  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var t = btn.getAttribute("data-tab");
      document.querySelectorAll(".tab-btn").forEach(function (b) {
        b.classList.remove("border-teal-500", "text-teal-700", "bg-teal-50/50");
        b.classList.add("border-transparent", "text-slate-500");
      });
      btn.classList.add("border-teal-500", "text-teal-700", "bg-teal-50/50");
      btn.classList.remove("border-transparent", "text-slate-500");
      document.querySelectorAll(".tab-panel").forEach(function (p) {
        p.classList.add("hidden");
      });
      var panel = document.getElementById("panel-" + t);
      if (panel) panel.classList.remove("hidden");
    });
  });

  monthlyAS();
  patho();
  stay("chartStay");
  costs();
  costBar();
  demoAge();
  gender();
  stay("chartStayDemo");

  /** iPad / iPhone : fetch → blob hors pile « user gesture » → Safari bloque ou échoue ; on garde le lien HTML natif. */
  function preferNativeExportLink() {
    var ua = navigator.userAgent || "";
    if (/iPhone|iPod/i.test(ua)) return true;
    if (/iPad/i.test(ua)) return true;
    if (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1) return true;
    return false;
  }

  /** Téléchargement fiable (évite target=_blank + download ignorés pour les PDF / onglets bloqués). */
  function parseContentDispositionFilename(cd) {
    if (!cd || typeof cd !== "string") return null;
    var m = /\bfilename\*=UTF-8''([^;\n]+)/i.exec(cd);
    if (m) {
      try {
        return decodeURIComponent(m[1].trim());
      } catch (e) {
        return m[1].trim();
      }
    }
    m = /\bfilename\*=([^;\n]+)/i.exec(cd);
    if (m) {
      var raw = m[1].trim().replace(/^["']|["']$/g, "");
      if (/^UTF-8''/i.test(raw)) {
        try {
          return decodeURIComponent(raw.slice(7));
        } catch (e2) {
          /* ignore */
        }
      }
    }
    m = /\bfilename="((?:\\.|[^"])*)"/i.exec(cd);
    if (m) return m[1].replace(/\\(.)/g, "$1");
    m = /\bfilename=([^;\n]+)/i.exec(cd);
    if (m) return m[1].trim().replace(/^["']|["']$/g, "");
    return null;
  }

  function triggerBlobDownload(url, fallbackName) {
    return fetch(url, { credentials: "same-origin", cache: "no-store" }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (t) {
          var hint = t && t.length && t.length < 400 ? t.trim().slice(0, 400) : "";
          throw new Error(res.status + (hint ? " — " + hint : ""));
        });
      }
      var name = parseContentDispositionFilename(res.headers.get("Content-Disposition")) || fallbackName;
      return res.blob().then(function (blob) {
        var a = document.createElement("a");
        var u = URL.createObjectURL(blob);
        a.href = u;
        a.download = name;
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        /* Ne pas révoquer tout de suite : Chrome laisse alors un .crdownload « Non confirmé » incomplet. */
        setTimeout(function () {
          a.remove();
          URL.revokeObjectURL(u);
        }, 120000);
      });
    });
  }

  /**
   * PDF maquette (Playwright, réponse longue) : éviter <a download target=_blank> qui coupe souvent le flux.
   * Nouvel onglet sans attribut download — le serveur envoie Content-Disposition: attachment.
   */
  document.querySelectorAll("a.maquette-pdf-export").forEach(function (link) {
    link.addEventListener("click", function (e) {
      if (preferNativeExportLink()) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      var href = link.getAttribute("href");
      if (!href) return;
      e.preventDefault();
      var w = window.open(href, "_blank", "noopener,noreferrer");
      if (!w) {
        window.location.href = href;
      }
    });
  });

  document.querySelectorAll("a.export-blob-link").forEach(function (link) {
    link.addEventListener("click", function (e) {
      if (preferNativeExportLink()) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      var href = link.getAttribute("href");
      if (!href) return;
      e.preventDefault();
      if (link.getAttribute("aria-busy") === "true") return;
      var fallback = link.getAttribute("data-download-filename") || "export";
      link.setAttribute("aria-busy", "true");
      link.classList.add("pointer-events-none", "opacity-70");
      triggerBlobDownload(href, fallback)
        .catch(function (err) {
          window.alert("Téléchargement impossible : " + (err && err.message ? err.message : String(err)));
        })
        .finally(function () {
          link.setAttribute("aria-busy", "false");
          link.classList.remove("pointer-events-none", "opacity-70");
        });
    });
  });

})();
