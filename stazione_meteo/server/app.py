from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import random
from threading import Thread
import time
import serial
import requests
import os
import csv

app = Flask(__name__)

# ==============================
#       SERIALE ARDUINO
# ==============================
SERIAL_PORT = "COM8"
BAUD_RATE = 9600

# ==============================
#       GEOLOCALIZZAZIONE
# ==============================
def get_coordinates_from_ip():
    try:
        r = requests.get("http://ip-api.com/json", timeout=5)
        data = r.json()
        return data.get("lat", 41.9), data.get("lon", 12.5)
    except Exception:
        return 41.9, 12.5

LAT, LON = get_coordinates_from_ip()

# ==============================
#          API METEO
# ==============================
API_UPDATE_INTERVAL = 60

meteo_api_cache = {
    "pressure": 1015.0,
    "precip_hourly": [],    
    "timestamps": [],       
    "last_update": None,
    "data_timestamp": None
}

# ==============================
# MEMORIA RISCHIO FRANA
# ==============================
risk_history = []
MAX_RISK_POINTS = 360

# ==============================
#      STORICO CSV
# ==============================
CSV_FILE = "storico_dati.csv"
CSV_HEADER = [
    "timestamp",
    "temperature",
    "humidity",
    "pressure",
    "pioggia_3h",
    "pioggia_presente"
]
#Crea il file
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)


# ==============================
#       SENSORE PIOGGIA
# ==============================
SOGLIA_PIOGGIA = 500

# ==============================
#     PIOGGIA (SENSORE)
# ==============================
pioggia_istantanea = False

# =====================
#    DATI (REAL + SIM)
# =====================

dati_giorno = []

# =====================
#       FUNZIONI
# =====================

def aggiorna_meteo_api():
    global meteo_api_cache
    now = datetime.now()

    if (
        meteo_api_cache["last_update"] is None or
        (now - meteo_api_cache["last_update"]).seconds >= API_UPDATE_INTERVAL
    ):
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={LAT}&longitude={LON}"
                "&hourly=pressure_msl,precipitation"
                "&forecast_days=1"
            )
            r = requests.get(url, timeout=5)
            data = r.json()

            meteo_api_cache["pressure"] = data["hourly"]["pressure_msl"][-1]
            meteo_api_cache["precip_hourly"] = data["hourly"]["precipitation"]
            meteo_api_cache["timestamps"] = data["hourly"]["time"]
            meteo_api_cache["last_update"] = now
            meteo_api_cache["data_timestamp"] = data["hourly"]["time"][-1]

        except Exception:
            pass

    return meteo_api_cache

def pioggia_cumulata_ore(n_ore):
    """
    Ritorna la pioggia cumulata (mm) nelle ultime n ore
    usando SOLO dati API meteo.
    """
    meteo = aggiorna_meteo_api()

    if not meteo["precip_hourly"]:
        return 0.0

    return round(sum(meteo["precip_hourly"][-n_ore:]), 1)

def calcola_medi(dati):
    if not dati:
        return {"temperature": 0, "humidity": 0, "pressure": 0, "rain": 0}

    n = len(dati)
    media_temp = round(sum(d["temperature"] for d in dati) / n, 1)
    media_hum = round(sum(d["humidity"] for d in dati) / n, 1)
    media_press = round(sum(d["pressure"] for d in dati) / n, 1)
    totale_rain = round(sum(d["rain"] for d in dati), 1)

    return {
        "temperature": media_temp,
        "humidity": media_hum,
        "pressure": media_press,
        "rain": totale_rain
    }

def calcola_rischio(medie):
    score = 0

    if medie["temperature"] > 26 or medie["temperature"] < 19:
        score += 1
    if medie["humidity"] > 75:
        score += 1
    if medie["rain"] > 10:
        score += 1

    if score == 0:
        indice = "LOW"
        spiegazione = "Temperature nella norma, bassa umidità e poca pioggia."
    elif score == 1 or score == 2:
        indice = "MEDIUM"
        spiegazione = "Condizioni leggermente critiche: una o due variabili fuori soglia."
    else:
        indice = "HIGH"
        spiegazione = "Condizioni critiche: più variabili fuori soglia, rischio elevato."

    return {"indice": indice, "spiegazione": spiegazione}

def calcola_rischio_istantaneo(dati, finestra=4):
    if len(dati) < 2:
        return {
            "indice": "LOW",
            "spiegazione": "Dati insufficienti per una valutazione istantanea affidabile."
        }

    ultimi = dati[-finestra:]

    temp_media = sum(d["temperature"] for d in ultimi) / len(ultimi)
    hum_media = sum(d["humidity"] for d in ultimi) / len(ultimi)
    rain_tot = sum(d["rain"] for d in ultimi)

    score = 0
    if temp_media > 26 or temp_media < 19:
        score += 1
    if hum_media > 75:
        score += 1
    if rain_tot > 3:
        score += 1

    if score == 0:
        indice = "LOW"
    elif score == 1:
        indice = "MEDIUM"
    else:
        indice = "HIGH"

    spiegazione = (
        f"Il rischio istantaneo è valutato come {indice} sulla base "
        f"delle ultime {len(ultimi)} misurazioni. "
        f"In questo intervallo la temperatura media è stata {temp_media:.1f} °C, "
        f"l'umidità media {hum_media:.1f} % e le precipitazioni cumulate {rain_tot:.1f} mm. "
        "Questa analisi riflette condizioni locali recenti e può variare rapidamente nel tempo."
    )

    return {"indice": indice, "spiegazione": spiegazione}

def calcola_trend(dati, finestra=6):
    if len(dati) < finestra * 2:
        return {"temperature": "→", "humidity": "→", "pressure": "→"}

    recenti = dati[-finestra:]
    precedenti = dati[-2*finestra:-finestra]

    def trend(v_recenti, v_precedenti):
        diff = sum(v_recenti)/len(v_recenti) - sum(v_precedenti)/len(v_precedenti)
        if diff > 0.3:
            return "↑"
        elif diff < -0.3:
            return "↓"
        else:
            return "→"

    return {
        "temperature": trend(
            [d["temperature"] for d in recenti],
            [d["temperature"] for d in precedenti]
        ),
        "humidity": trend(
            [d["humidity"] for d in recenti],
            [d["humidity"] for d in precedenti]
        ),
        "pressure": trend(
            [d["pressure"] for d in recenti],
            [d["pressure"] for d in precedenti]
        )
    }

def get_meteo_external_probability():
    return random.randint(20, 80)

def stima_probabilita_pioggia(medie):
    prob_api = get_meteo_external_probability()

    fattore_locale = 0
    if medie["humidity"] > 75:
        fattore_locale += 10
    if medie["pressure"] < 1010:
        fattore_locale += 10
    if medie["rain"] > 2:
        fattore_locale += 15

    prob_finale = min(prob_api + fattore_locale, 100)

    spiegazione = (
        f"La probabilità di pioggia stimata per la giornata è del {prob_finale}%. "
        f"Il valore deriva dall'integrazione di previsioni meteo esterne ({prob_api}%) "
        "con le condizioni locali misurate dalla stazione."
    )

    return {"probabilita": prob_finale, "spiegazione": spiegazione}

def calcola_probabilita_frana(dati_correnti, rischio_precedente=None):
    pioggia = dati_correnti["rain"]
    umidita = dati_correnti["humidity"]
    pressione = dati_correnti["pressure"]

    p_pioggia = min(pioggia / 100.0, 1.0)
    p_umidita = max((umidita - 60) / 40, 0)
    p_pressione = max((1015 - pressione) / 20, 0)

    probabilita = 0.5 * p_pioggia + 0.3 * p_umidita + 0.2 * p_pressione

    if rischio_precedente is not None:
        probabilita = 0.7 * rischio_precedente + 0.3 * probabilita

    probabilita = max(0, min(probabilita, 1))
    probabilita_pct = probabilita * 100

    if probabilita_pct < 33:
        classe = "LOW"
    elif probabilita_pct < 66:
        classe = "MEDIUM"
    else:
        classe = "HIGH"

    return probabilita_pct, classe

def leggi_storico_csv():
    """
    Legge lo storico dal CSV e ritorna una lista di dizionari.
    """
    dati = []

    if not os.path.exists(CSV_FILE):
        return dati

    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dati.append(row)

    return dati

# =====================
# THREAD SERIALE ARDUINO
# =====================
def aggiorna_dati_seriale():
    global pioggia_istantanea
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        try:
            parts = {}
            for p in line.split(";"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    parts[k.strip()] = v.strip()

            meteo_api = aggiorna_meteo_api()

            pioggia_istantanea = float(parts["RAIN"]) < SOGLIA_PIOGGIA


            nuovo_dato = {
                "timestamp": datetime.now(),
                "temperature": float(parts["TEMP"]),
                "humidity": float(parts["HUM"]),
                "pressure": meteo_api["pressure"],
                "rain": pioggia_cumulata_ore(3)

            }

            dati_giorno.append(nuovo_dato)
            if len(dati_giorno) > 100:
                dati_giorno.pop(0)

            #storico csv
            with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    nuovo_dato["timestamp"].isoformat(),
                    nuovo_dato["temperature"],
                    nuovo_dato["humidity"],
                    nuovo_dato["pressure"],
                    pioggia_cumulata_ore(3),
                    "PRESENTE" if pioggia_istantanea else "ASSENTE"
    ])


            rischio_precedente = (
                risk_history[-1]["probabilita"] / 100
                if risk_history else None
            )

            probabilita, classe = calcola_probabilita_frana(
                nuovo_dato,
                rischio_precedente
            )

            risk_history.append({
                "timestamp": nuovo_dato["timestamp"].strftime("%H:%M:%S"),
                "probabilita": probabilita,
                "classe": classe
            })

            if len(risk_history) > MAX_RISK_POINTS:
                risk_history.pop(0)

        except Exception:
            print("Errore parsing seriale:", line)

        time.sleep(2)

# =====================
# SIMULATORE (NON IN USO)
# =====================
def aggiorna_dati_simulati():
    while True:
        nuovo_dato = genera_misurazione()
        dati_giorno.append(nuovo_dato)
        if len(dati_giorno) > 100:
            dati_giorno.pop(0)

        rischio_precedente = (
            risk_history[-1]["probabilita"] / 100
            if risk_history else None
        )

        probabilita, classe = calcola_probabilita_frana(
            nuovo_dato,
            rischio_precedente
        )

        risk_history.append({
            "timestamp": nuovo_dato["timestamp"].strftime("%H:%M:%S"),
            "probabilita": probabilita,
            "classe": classe
        })

        if len(risk_history) > MAX_RISK_POINTS:
            risk_history.pop(0)

        time.sleep(10)

# =====================
#       ROUTES
# =====================
@app.route("/")
def home():
    medie = calcola_medi(dati_giorno)
    pioggia_3h = pioggia_cumulata_ore(3)

    if dati_giorno:
       ultimo = dati_giorno[-1]
       probabilita, classe = calcola_probabilita_frana(ultimo)
    else:
        probabilita, classe = 0.0, "LOW"

    rischio = {
        "indice": classe,
        "spiegazione": f"Rischio medio stimato su base probabilistica ({probabilita:.1f}%)."
    }

    trend = calcola_trend(dati_giorno)
    pioggia_prevista = stima_probabilita_pioggia(medie)

    return render_template(
        "home.html",
        medie=medie,
        rischio=rischio,
        trend=trend,
        pioggia_prevista=pioggia_prevista,
        pioggia_3h=pioggia_3h,
    )


@app.route("/dashboard")
def dashboard():
    ultimo = dati_giorno[-1] if dati_giorno else genera_misurazione()

    pioggia_presente = "PRESENTE" if pioggia_istantanea else "ASSENTE"

    timestamps = [d["timestamp"].strftime("%H:%M:%S") for d in dati_giorno]
    temperature = [d["temperature"] for d in dati_giorno]
    humidity = [d["humidity"] for d in dati_giorno]
    pressure = [d["pressure"] for d in dati_giorno]
    rain = [d["rain"] for d in dati_giorno]

    return render_template(
        "dashboard.html",
        ultimo=ultimo,
        pioggia_presente=pioggia_presente,
        grafici={
            "timestamps": timestamps,
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "rain": rain,
        }
    )

@app.route("/risk")
def risk():
    medie = calcola_medi(dati_giorno)
    rischio_istantaneo = calcola_rischio_istantaneo(dati_giorno)

    ultimo = dati_giorno[-1]
    probabilita, classe = calcola_probabilita_frana(ultimo)

    rischio = {
        "indice": classe,
        "spiegazione": f"Rischio stimato su base probabilistica ({probabilita:.1f}%)."
    }

    return render_template(
        "risk.html",
        medie=medie,
        rischio=rischio,
        rischio_istantaneo=rischio_istantaneo
    )

@app.route("/storico")
def storico():
    storico_dati = leggi_storico_csv()

    return render_template(
        "storico.html",
        storico=storico_dati
    )

# =====================
#      API JSON
# =====================
@app.route("/api/ultimo")
def api_ultimo():
    return jsonify(dati_giorno[-1] if dati_giorno else {})

@app.route("/api/medie")
def api_medie():
    return jsonify(calcola_medi(dati_giorno))

@app.route("/api/rischio")
def api_rischio():
    return jsonify(calcola_rischio(calcola_medi(dati_giorno)))

@app.route("/api/grafici")
def api_grafici():
    return jsonify({
        "timestamps": [d["timestamp"].strftime("%H:%M:%S") for d in dati_giorno],
        "temperature": [d["temperature"] for d in dati_giorno],
        "humidity": [d["humidity"] for d in dati_giorno],
        "pressure": [d["pressure"] for d in dati_giorno],
        "rain": [d["rain"] for d in dati_giorno]
    })

@app.route("/api/meteo/data_timestamp")
def api_meteo_data_timestamp():
    ts = meteo_api_cache.get("data_timestamp")

    if ts is None:
        return jsonify({"orario": None})

    # ts è tipo "2026-02-19T14:00"
    return jsonify({
        "orario": ts.split("T")[1]
    })


@app.route("/api/pioggia/<int:ore>")
def api_pioggia(ore):
    return jsonify({
        "ore": ore,
        "pioggia": pioggia_cumulata_ore(ore)
    })


# ========================
# API TREND RISCHIO FRANA
# ========================
@app.route("/api/rischio/trend")
def api_trend_rischio():
    return jsonify(risk_history)

# =====================
#      RUN SERVER
# =====================
if __name__ == "__main__":
    Thread(target=aggiorna_dati_seriale, daemon=True).start()
    app.run(debug=False, use_reloader=False)
