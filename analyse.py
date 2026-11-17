# Radon-Analyse – nur Python-Bordmittel (kein pandas)
import csv, json, sys, math, statistics
from collections import defaultdict
from datetime import datetime

PFAD = sys.argv[1]
AUSGABE = sys.argv[2]

with open(PFAD, encoding="utf-8") as f:
    reader = csv.reader(f)
    kopf = next(reader)
    zeilen = list(reader)

idx = {name: i for i, name in enumerate(kopf)}
print("Zeilen:", len(zeilen))

# Radon-Spalten und zugehörige Betriebszeit
radon = {}
for name in kopf:
    if "Radon" in name:
        raum = name.split(" – ")[0]
        bz = raum + " – Betriebszeit (min)"
        radon[raum] = (idx[name], idx.get(bz))
andere = [n for n in kopf[2:] if "Radon" not in n and "Betriebszeit" not in n]

# Stündliche Sammlung: stunden[variable][ 'YYYY-MM-DD HH' ] = [werte]
stunden = defaultdict(lambda: defaultdict(list))
info = defaultdict(lambda: {"n": 0, "erste": None, "letzte": None, "verworfen": 0})

for z in zeilen:
    lokal = z[1]
    h = lokal[:13]
    for raum, (ri, bi) in radon.items():
        if ri < len(z) and z[ri] != "":
            v = float(z[ri])
            bz = float(z[bi]) if bi is not None and z[bi] != "" else None
            i = info[raum]
            # Anlaufphase nach Neustart verwerfen (Sensor braucht ~1 h)
            if bz is not None and bz < 60:
                i["verworfen"] += 1
                continue
            i["n"] += 1
            i["erste"] = i["erste"] or lokal
            i["letzte"] = lokal
            stunden[raum][h].append(v)
    for name in andere:
        j = idx[name]
        if j < len(z) and z[j] != "":
            stunden[name][h].append(float(z[j]))
            i = info[name]
            i["n"] += 1
            i["erste"] = i["erste"] or lokal
            i["letzte"] = lokal

stdmittel = {var: {h: sum(v) / len(v) for h, v in d.items()} for var, d in stunden.items()}

def tageswerte(var):
    t = defaultdict(list)
    for h, v in stdmittel[var].items():
        t[h[:10]].append(v)
    # nur Tage mit mindestens 12 Stunden Daten
    return {d: sum(v) / len(v) for d, v in t.items() if len(v) >= 12}

def pearson(a, b):
    n = len(a)
    if n < 10:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)

def raenge(a):
    s = sorted(range(len(a)), key=lambda i: a[i])
    r = [0] * len(a)
    for rang, i in enumerate(s):
        r[i] = rang
    return r

def spearman(a, b):
    return pearson(raenge(a), raenge(b))

def paare(x, y):
    gemeinsam = sorted(set(x) & set(y))
    return [x[k] for k in gemeinsam], [y[k] for k in gemeinsam]

raeume = list(radon.keys())
erg = {"info": info, "raeume": raeume}

# Kennzahlen pro Raum (auf Stundenmitteln)
kenn = {}
for r in raeume:
    w = sorted(stdmittel[r].values())
    n = len(w)
    kenn[r] = {
        "stunden": n,
        "mittel": round(sum(w) / n, 1),
        "median": round(statistics.median(w), 1),
        "p95": round(w[int(0.95 * (n - 1))], 1),
        "max": round(w[-1], 1),
        "ueber100": round(100 * sum(x > 100 for x in w) / n, 1),
        "ueber300": round(100 * sum(x > 300 for x in w) / n, 1),
    }
erg["kennzahlen"] = kenn

# Monatsmittel
monat = {}
for var in raeume + andere:
    m = defaultdict(list)
    for h, v in stdmittel[var].items():
        m[h[:7]].append(v)
    monat[var] = {k: round(sum(v) / len(v), 1) for k, v in sorted(m.items())}
erg["monat"] = monat

# Tagesgang (Stunde 0–23)
tagesgang = {}
for var in raeume + andere:
    g = defaultdict(list)
    for h, v in stdmittel[var].items():
        g[int(h[11:13])].append(v)
    tagesgang[var] = [round(sum(g[s]) / len(g[s]), 1) if g[s] else None for s in range(24)]
erg["tagesgang"] = tagesgang

# Tagesreihen
tag = {var: tageswerte(var) for var in raeume + andere}
AT = "Wetter – Temperatur 2 m (°C)"
# Temperaturdifferenz innen–außen (Mittel aus Küche/Schlafzimmer)
innen = {}
for k in ("Kueche (Luft) – Temperatur innen (°C)", "Schlafzimmer – Temperatur innen (°C)"):
    for d, v in tag.get(k, {}).items():
        innen.setdefault(d, []).append(v)
tag["ΔT innen–außen"] = {d: sum(v) / len(v) - tag[AT][d] for d, v in innen.items() if d in tag[AT]}
erg["tag"] = {var: {d: round(v, 2) for d, v in sorted(s.items())} for var, s in tag.items()}

# Korrelationen Tagesmittel Radon vs. Umwelt
umwelt = [n for n in andere] + ["ΔT innen–außen"]
korr = {}
for r in raeume:
    korr[r] = {}
    for u in umwelt:
        a, b = paare(tag[r], tag[u])
        if len(a) >= 10:
            korr[r][u] = {"pearson": round(pearson(a, b), 2), "spearman": round(spearman(a, b), 2), "n": len(a)}
erg["korr_tag"] = korr

# Kurzfristig: stündliche Druckänderung (3 h) vs. Radon-Abweichung vom 24-h-Mittel
P = "Wetter – Luftdruck (hPa)"
def zeit(h):
    return datetime.strptime(h, "%Y-%m-%d %H")
druck = {zeit(h): v for h, v in stdmittel.get(P, {}).items()}
from datetime import timedelta
dp = {}
for t, v in druck.items():
    t3 = t - timedelta(hours=3)
    if t3 in druck:
        dp[t] = v - druck[t3]
korr_dp = {}
for r in raeume:
    rs = {zeit(h): v for h, v in stdmittel[r].items()}
    a, b = [], []
    for t, v in rs.items():
        if t not in dp:
            continue
        fenster = [rs.get(t - timedelta(hours=k)) for k in range(-12, 12)]
        fenster = [x for x in fenster if x is not None]
        if len(fenster) < 18:
            continue
        a.append(v - sum(fenster) / len(fenster))
        b.append(dp[t])
    if len(a) > 50:
        korr_dp[r] = {"pearson": round(pearson(a, b), 2), "n": len(a)}
erg["korr_druckaenderung"] = korr_dp

# Korrelationsmatrix zwischen Räumen (Tagesmittel)
mat = {}
for r1 in raeume:
    mat[r1] = {}
    for r2 in raeume:
        a, b = paare(tag[r1], tag[r2])
        mat[r1][r2] = round(pearson(a, b), 2) if len(a) >= 10 else None
erg["korr_raeume"] = mat

# Stündliche Reihen für Dashboard (Tageswerte reichen meist; Stunden für Wochen-Detail)
erg["stunde"] = {var: {h: round(v, 2) for h, v in sorted(d.items())} for var, d in stdmittel.items()}

with open(AUSGABE, "w", encoding="utf-8") as f:
    json.dump(erg, f, ensure_ascii=False)

# Konsolen-Zusammenfassung
print("\n== Erfassung ==")
for k, v in info.items():
    print(f"{k:55s} n={v['n']:6d} verworfen={v['verworfen']:4d} {v['erste']} → {v['letzte']}")
print("\n== Kennzahlen Radon (Stundenmittel, Bq/m³) ==")
for r, k in kenn.items():
    print(r, k)
print("\n== Monatsmittel ==")
for var, m in monat.items():
    print(var, m)
print("\n== Tagesgang Radon ==")
for r in raeume:
    print(r, tagesgang[r])
print("\n== Korrelation Tagesmittel ==")
for r in raeume:
    print(r)
    for u, k in korr[r].items():
        print(f"   {u:45s} r={k['pearson']:5} rho={k['spearman']:5} n={k['n']}")
print("\n== Druckänderung 3h vs Radon-Abweichung ==", korr_dp)
print("\n== Räume untereinander ==")
for r, m in mat.items():
    print(r, m)
