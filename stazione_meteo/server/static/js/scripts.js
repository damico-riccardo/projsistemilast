// scripts.js

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatValue(value, unit = "") {
  if (value === null || value === undefined) return "--";
  return value + unit;
}

function setRiskBadge(level) {
  const badge = document.getElementById("riskBadge");
  if (!badge) return;

  badge.className = "risk " + level;
  badge.textContent = level.toUpperCase();
}
// ==================================================
// AGGIUNTO: TREND PROBABILITÀ DI FRANA (HOME)
// ==================================================

async function aggiornaGraficoRischioFrana() {
    const container = document.getElementById("grafico_rischio");
    if (!container) return; // siamo su un'altra pagina

    try {
        const response = await fetch("/api/rischio/trend");
        const dati = await response.json();

        if (!dati || dati.length === 0) return;

        const timestamps = dati.map(d => d.timestamp);
        const probabilita = dati.map(d => d.probabilita);

        const trace = {
            x: timestamps,
            y: probabilita,
            type: "scatter",
            mode: "lines+markers",
            line: {
                color: "#dc2626",
                width: 3
            },
            marker: {
                size: 6
            },
            name: "Probabilità di frana (%)"
        };

        const layout = {
            yaxis: {
                title: "Probabilità (%)",
                range: [0, 100]
            },
            xaxis: {
                title: "Tempo"
            },
            margin: { t: 20 }
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true });

    } catch (err) {
        console.error("Errore grafico rischio frana:", err);
    }
}

// primo disegno + aggiornamento ogni 10s
document.addEventListener("DOMContentLoaded", () => {
    aggiornaGraficoRischioFrana();
    setInterval(aggiornaGraficoRischioFrana, 10000);
});

// ==========================
// Orario aggiornamento Open-Meteo
// ==========================
function aggiornaOrarioMeteo() {
    fetch("/api/meteo/data_timestamp")
        .then(res => res.json())
        .then(data => {
            if (!data.orario) return;

            const el = document.getElementById("meteoUpdateTime");
            if (!el) return;

            el.innerText =
                "Dati meteo (pressione e pioggia) aggiornati alle: " +
                data.orario;
        })
        .catch(() => {});
}

// Aggiornamento iniziale + refresh ogni 60s
document.addEventListener("DOMContentLoaded", () => {
    aggiornaOrarioMeteo();
    setInterval(aggiornaOrarioMeteo, 60000);
});
