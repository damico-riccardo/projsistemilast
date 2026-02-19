import time
import random
import requests

URL = "http://127.0.0.1:5000/upload"

soil = 35.0

while True:
    rain = max(0, random.gauss(2, 3))   # pioggia impulsiva
    temp = random.gauss(15, 2)

    # risposta lenta del suolo alla pioggia
    soil += 0.1 * rain
    soil -= 0.05
    soil = max(10, min(soil, 90))

    payload = {
        "temperature": round(temp, 1),
        "rain_mm": round(rain, 1),
        "soil_moisture": round(soil, 1)
    }

    r = requests.post(URL, json=payload)
    print(payload, r.status_code)

    time.sleep(5)
