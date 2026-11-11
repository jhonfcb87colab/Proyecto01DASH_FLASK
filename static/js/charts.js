/* Render de gráficas del dashboard con Chart.js */
(function () {
  if (typeof Chart === 'undefined') return;

  const PAGE = window.DASHBOARD_PAGE;
  const C = window.DASHBOARD_CHARTS || {};
  const charts = {};
  const PALETTE = ['#2563eb', '#f59e0b', '#0ea5e9', '#dc2626', '#7c3aed', '#ea580c', '#0891b2', '#e044a7', '#06b6d4', '#94a3b8'];

  function fmt(n, d = 0) {
    const x = Number(n);
    if (!isFinite(x)) return '—';
    return x.toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function el(id) { return document.getElementById(id); }
  function chart(id, cfg) {
    const node = el(id);
    if (!node) return;
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart(node, cfg);
  }
  function catStacked(stacked) {
    return {
      stacked,
      grid: { display: false, drawTicks: false },
      ticks: { font: { size: 10 }, maxRotation: 0, autoSkip: true },
      border: { display: false }
    };
  }
  function valScale(opts = {}) {
    return {
      stacked: !!opts.stacked,
      beginAtZero: true,
      max: opts.max,
      grid: { color: '#e2e8f0', drawTicks: false },
      ticks: { font: { size: 10 }, callback: opts.callback || ((v) => fmt(v, 0)) },
      border: { display: false }
    };
  }
  function tooltip(cb) {
    return { backgroundColor: 'rgba(15,23,42,.95)', padding: 11, cornerRadius: 9, callbacks: cb };
  }

  Chart.defaults.font.family = "'Segoe UI', system-ui, -apple-system, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = '#64748b';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.boxHeight = 8;
  Chart.defaults.plugins.legend.labels.padding = 13;
  Chart.defaults.plugins.legend.labels.font = { size: 10.5, weight: '600' };
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15,23,42,.95)';
  Chart.defaults.plugins.tooltip.padding = 11;
  Chart.defaults.plugins.tooltip.cornerRadius = 9;
  Chart.defaults.elements.bar.borderRadius = 4;
  Chart.defaults.elements.bar.borderSkipped = false;

  if (PAGE === 'principal' && C.piezas) {
    const d = C.piezas;
    chart('chartPiezas', {
      type: 'bar',
      data: {
        labels: d.labels,
        datasets: d.datasets.map((s) => ({
          label: s.label,
          data: s.data,
          _counts: s.counts,
          backgroundColor: s.color,
          borderWidth: 0,
          maxBarThickness: 34
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: tooltip({
            label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw, 1)}% (${fmt(ctx.dataset._counts ? ctx.dataset._counts[ctx.dataIndex] : 0)} guías)`
          })
        },
        scales: {
          x: { ...catStacked(true), title: { display: true, text: 'Número de piezas', font: { size: 10, weight: '700' } } },
          y: { ...valScale({ stacked: true, max: 100, callback: (v) => v + '%' }) }
        }
      }
    });
  }

  if (PAGE === 'confirmaciones' && C.conf) {
    const d = C.conf;
    chart('chartConf', {
      type: 'bar',
      data: {
        labels: d.labels,
        datasets: d.datasets.map((s) => ({ label: s.label, data: s.data, backgroundColor: s.color, borderWidth: 0, maxBarThickness: 48 }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', align: 'end', labels: { usePointStyle: true, padding: 12, font: { size: 10 } } },
          tooltip: tooltip({ label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw)} piezas confirmadas` })
        },
        scales: { x: catStacked(false), y: valScale({}) }
      }
    });
  }

  if (PAGE === 'vejez-comp' && C.vejezComp) {
    const d = C.vejezComp;
    chart('chartVejezComp', {
      type: 'bar',
      data: {
        labels: d.labels,
        datasets: d.datasets.map((s) => ({ label: s.label, data: s.data, _raw: s.raw, backgroundColor: s.color, borderWidth: 0, maxBarThickness: 42 }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: tooltip({
            label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw, 1)}% (${fmt(ctx.dataset._raw[ctx.dataIndex], 1)} días)`
          })
        },
        scales: { x: catStacked(true), y: { ...valScale({ stacked: true, max: 100, callback: (v) => v + '%' }) } }
      }
    });
  }

  if (PAGE === 'vejez-rez') {
    if (C.rezLine) {
      chart('chartRezLine', {
        type: 'line',
        data: {
          labels: C.rezLine.labels,
          datasets: [{
            label: 'Días de vejez',
            data: C.rezLine.values,
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37,99,235,.12)',
            fill: true,
            tension: 0.35,
            pointRadius: 2.5,
            pointHoverRadius: 5,
            pointBackgroundColor: '#2563eb',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: tooltip({ label: (ctx) => `${fmt(ctx.raw, 1)} días de vejez` }) },
          scales: {
            x: { ...catStacked(false), ticks: { font: { size: 9.5 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 18 } },
            y: valScale({})
          }
        }
      });
    }
    if (C.rezBar) {
      chart('chartRezBar', {
        type: 'bar',
        data: {
          labels: C.rezBar.labels,
          datasets: C.rezBar.datasets.map((s) => ({ label: s.label, data: s.data, backgroundColor: s.color, borderWidth: 0, maxBarThickness: 46 }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: tooltip({ label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw, 1)} días` }) },
          scales: { x: catStacked(true), y: valScale({ stacked: true }) }
        }
      });
    }
  }

  if (PAGE === 'tareas-estados') {
    if (C.tareasMes) {
      chart('chartTareasMes', {
        type: 'bar',
        data: {
          labels: C.tareasMes.labels,
          datasets: C.tareasMes.datasets.map((s) => ({ label: s.label, data: s.data, backgroundColor: s.color, borderWidth: 0, maxBarThickness: 26 }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: tooltip({ label: (ctx) => `${ctx.dataset.label}: ${ctx.raw == null ? 'sin datos' : fmt(ctx.raw, 1) + ' h'}` })
          },
          scales: { x: catStacked(false), y: { ...valScale({ callback: (v) => fmt(v) + ' h' }) } }
        }
      });
    }
    if (C.tareasPie) {
      chart('chartTareasPie', {
        type: 'doughnut',
        data: {
          labels: C.tareasPie.labels,
          datasets: [{
            data: C.tareasPie.values,
            backgroundColor: C.tareasPie.labels.map((_, i) => PALETTE[i % PALETTE.length]),
            borderWidth: 2,
            borderColor: '#fff',
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '60%',
          plugins: {
            legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 9, font: { size: 9.5 } } },
            tooltip: tooltip({ label: (ctx) => `${ctx.label}: ${fmt(ctx.raw)} pendientes` })
          }
        }
      });
    }
  }

  if (PAGE === 'tareas-comparativo') {
    if (C.compMes) {
      chart('chartCompMes', {
        type: 'bar',
        data: {
          labels: C.compMes.labels,
          datasets: [
            { label: 'Número de tareas', data: C.compMes.tasks, backgroundColor: '#2563eb', borderRadius: 4, maxBarThickness: 24, yAxisID: 'y' },
            { label: 'Promedio respuesta (h)', data: C.compMes.avg, type: 'line', borderColor: '#f59e0b', backgroundColor: '#f59e0b', tension: 0.35, pointRadius: 3, borderWidth: 2.5, yAxisID: 'y1' }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', align: 'end' },
            tooltip: tooltip({
              label: (ctx) => ctx.dataset.type === 'line'
                ? `Promedio: ${ctx.raw == null ? '—' : fmt(ctx.raw, 1) + ' h'}`
                : `Tareas: ${fmt(ctx.raw)}`
            })
          },
          scales: {
            x: catStacked(false),
            y: { ...valScale({}) },
            y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => fmt(v) + ' h' }, border: { display: false } }
          }
        }
      });
    }
    if (C.compAnual) {
      chart('chartCompAnual', {
        type: 'bar',
        data: {
          labels: C.compAnual.labels,
          datasets: [
            { label: 'Año anterior', data: C.compAnual.prev, backgroundColor: '#94a3b8', borderWidth: 0, maxBarThickness: 20 },
            { label: 'Año actual', data: C.compAnual.cur, backgroundColor: '#2563eb', borderWidth: 0, maxBarThickness: 20 },
            { label: '% diferencia', data: C.compAnual.diff, type: 'line', borderColor: '#dc2626', backgroundColor: '#dc2626', tension: 0.35, pointRadius: 2.5, borderWidth: 2, borderDash: [4, 3], yAxisID: 'y1' }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', align: 'end' },
            tooltip: tooltip({
              label: (ctx) => ctx.dataset.label === '% diferencia'
                ? `Diferencia: ${ctx.raw == null ? '—' : (ctx.raw >= 0 ? '+' : '') + fmt(ctx.raw, 1) + '%'}`
                : `${ctx.dataset.label}: ${ctx.raw == null ? '—' : fmt(ctx.raw, 1) + ' h'}`
            })
          },
          scales: {
            x: catStacked(false),
            y: { ...valScale({}) },
            y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => fmt(v) + '%' }, border: { display: false } }
          }
        }
      });
    }
    if (C.compRegional) {
      chart('chartCompRegional', {
        type: 'bar',
        data: {
          labels: C.compRegional.labels,
          datasets: [
            { label: 'Guías', data: C.compRegional.guias, backgroundColor: '#2563eb', borderRadius: 4, maxBarThickness: 32, yAxisID: 'y' },
            { label: 'Promedio respuesta (h)', data: C.compRegional.avg, type: 'line', borderColor: '#f59e0b', backgroundColor: '#f59e0b', tension: 0.35, pointRadius: 3, borderWidth: 2.5, yAxisID: 'y1' }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', align: 'end' },
            tooltip: tooltip({
              label: (ctx) => ctx.dataset.type === 'line'
                ? `Promedio: ${ctx.raw == null ? '—' : fmt(ctx.raw, 1) + ' h'}`
                : `Guías: ${fmt(ctx.raw)}`
            })
          },
          scales: {
            x: { ...catStacked(false), ticks: { font: { size: 9.5 }, maxRotation: 35, autoSkip: false } },
            y: valScale({}),
            y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => fmt(v) + ' h' }, border: { display: false } }
          }
        }
      });
    }
  }

  if (PAGE === 'procesos' && C.procesosBar) {
    chart('chartProcesosBar', {
      type: 'bar',
      data: {
        labels: C.procesosBar.labels,
        datasets: [{
          label: 'Registros',
          data: C.procesosBar.values,
          backgroundColor: C.procesosBar.labels.map((_, i) => PALETTE[i % PALETTE.length]),
          borderWidth: 0,
          maxBarThickness: 26
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: tooltip({ label: (ctx) => `${fmt(ctx.raw)} registros` }) },
        scales: {
          x: valScale({}),
          y: { grid: { display: false }, ticks: { font: { size: 9.5 }, autoSkip: false }, border: { display: false } }
        }
      }
    });
  }
})();
