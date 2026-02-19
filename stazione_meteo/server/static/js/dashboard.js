// ==========================
// dashboard.js
// ==========================

// Funzioni 
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
}

function setRiskBadge(risk) {
    const badge = document.getElementById("riskBadge");
    if (!badge) return;
    badge.innerText = risk.toUpperCase();
    badge.className = "risk " + risk.toLowerCase();
}

// ==========================
// Pioggia cumulata (API)   // MOD
// ==========================
let rainIntervalHours = 3;   // MOD

function aggiornaPioggiaCumulata() {   // MOD
    fetch(`/api/pioggia/${rainIntervalHours}`)
        .then(res => res.json())
        .then(data => {
            setText("rainValue", data.pioggia.toFixed(1) + " mm");
        })
        .catch(err => console.error("Errore fetch pioggia:", err));
}

// Aggiorna le card con i valori in tempo reale
function updateDashboard(data) {
    setText("tempValue", data.temperature + " °C");
    setText("humValue", data.humidity + " %");
    setText("pressValue", data.pressure + " hPa");
    setText("windValue", data.wind || "-- km/h");

    // ⚠️ NON aggiorniamo più la pioggia da qui (ora arriva solo da API cumulata)  // MOD

    setRiskBadge(data.risk || "low");
}

// Fetch dati ultimi valori
function aggiornaValori() {
    fetch("/api/ultimo")
        .then(res => res.json())
        .then(data => {
            fetch("/api/rischio")
                .then(res => res.json())
                .then(riskData => {
                    updateDashboard({
                        temperature: data.temperature,
                        humidity: data.humidity,
                        pressure: data.pressure,
                        wind: data.wind || "--",
                        risk: riskData.indice
                    });
                });
        })
        .catch(err => console.error("Errore fetch valori:", err));
}

// Fetch dati grafici
function aggiornaGrafici() {
    fetch("/api/grafici")
        .then(res => res.json())
        .then(data => {
            Plotly.react('tempGraph', [{
                x: data.timestamps,
                y: data.temperature,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#38bdf8' },
                name: 'Temperatura °C'
            }]);

            Plotly.react('humGraph', [{
                x: data.timestamps,
                y: data.humidity,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#facc15' },
                name: 'Umidità %'
            }]);

            Plotly.react('pressGraph', [{
                x: data.timestamps,
                y: data.pressure,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#22c55e' },
                name: 'Pressione hPa'
            }]);
        })
        .catch(err => console.error("Errore fetch grafici:", err));
}

// Inizializzazione al caricamento pagina
document.addEventListener("DOMContentLoaded", () => {

    // ===== collegamento menu a tendina pioggia =====  // MOD
    const select = document.getElementById("rainInterval");
    if (select) {
        rainIntervalHours = parseInt(select.value);
        aggiornaPioggiaCumulata();

        select.addEventListener("change", () => {
            rainIntervalHours = parseInt(select.value);
            aggiornaPioggiaCumulata();
        });

        setInterval(aggiornaPioggiaCumulata, 10000);
    }

    aggiornaValori();
    aggiornaGrafici();
    setInterval(aggiornaValori, 10000);
    setInterval(aggiornaGrafici, 10000);
});
