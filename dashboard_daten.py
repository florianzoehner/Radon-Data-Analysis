# Bereitet ergebnis.json kompakt fürs Dashboard auf
import json, math, sys

e = json.load(open(sys.argv[1], encoding="utf-8"))
t = e["tag"]
URLAUB = {"2026-08-0%d" % i for i in range(1, 7)}

def pearson(a, b):
    n = len(a); ma = sum(a) / n; mb = sum(b) / n
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(
        sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))

raeume = ["Wohnzimmer", "Kueche", "Buero", "Schlafzimmer", "Kueche - Sockel", "Technikraum", "Werkstatt"]
wohn = ["Wohnzimmer", "Kueche", "Buero", "Schlafzimmer"]
neben = ["Technikraum", "Werkstatt"]
AT = "Wetter – Temperatur 2 m (°C)"

faktoren = {
    "Außentemperatur": AT,
    "Bodentemp. 54 cm": "Wetter – Bodentemperatur 54 cm (°C)",
    "Wind": "Wetter – Wind 10 m (km/h)",
    "Luftdruck": "Wetter – Luftdruck (hPa)",
    "ΔT innen–außen": "ΔT innen–außen",
    "CO₂ Küche": "Kueche (Luft) – CO₂ (ppm)",
}
korr = {}
for r in raeume:
    korr[r] = {}
    for name, var in faktoren.items():
        k = [d for d in t[r] if d in t[var] and d not in URLAUB]
        korr[r][name] = round(pearson([t[r][d] for d in k], [t[var][d] for d in k]), 2)

tage = sorted(set().union(*[t[r].keys() for r in raeume]))
def reihe(var):
    return [t[var].get(d) for d in tage]

def gruppe(liste, d):
    w = [t[r][d] for r in liste if d in t[r]]
    return sum(w) / len(w) if w else None

streu = []
for d in tage:
    if d in t[AT]:
        streu.append({"d": d, "t": t[AT][d], "w": gruppe(wohn, d), "n": gruppe(neben, d), "u": d in URLAUB})

out = {
    "tage": tage,
    "radon": {r: reihe(r) for r in raeume},
    "aussen": reihe(AT),
    "co2": reihe("Kueche (Luft) – CO₂ (ppm)"),
    "kenn": e["kennzahlen"],
    "monat": {r: e["monat"][r] for r in raeume},
    "tagesgang": {r: e["tagesgang"][r] for r in raeume},
    "korr": korr,
    "streu": streu,
    "druck3h": e["korr_druckaenderung"],
}
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("ok", len(tage), "Tage")
