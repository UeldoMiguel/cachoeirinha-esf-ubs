# -*- coding: utf-8 -*-
"""Baixa do OpenStreetMap a malha viária e o limite de Cachoeirinha/RS.

Gera, no diretório corrente: osm_geo.json, osm_streets.json, boundary.json
e _osm_raw_geom.json (traçado completo das vias, insumo do lines_osm.py).
A consulta é restrita por bounding box porque existe outra Cachoeirinha (PE)
com o mesmo nome e mesmo admin_level.
"""
import json
import urllib.parse
import urllib.request

BBOX = "-30.05,-51.25,-29.85,-50.95"
ENDPOINT = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "cachoeirinha-esf-ubs/1.0"}


def overpass(query):
    req = urllib.request.Request(
        ENDPOINT, data=urllib.parse.urlencode({"data": query}).encode(), headers=UA
    )
    return json.load(urllib.request.urlopen(req, timeout=240))


def ruas():
    d = overpass(
        '[out:json][timeout:180];\n'
        'rel["boundary"="administrative"]["admin_level"="8"]["name"="Cachoeirinha"](%s);\n'
        'map_to_area->.a;\n'
        '(way(area.a)["highway"]["name"];);\n'
        'out center tags;' % BBOX
    )
    agg = {}
    for e in d["elements"]:
        t = e.get("tags", {})
        nome, c = t.get("name"), e.get("center")
        if not nome or not c:
            continue
        a = agg.setdefault(nome, {"lat": 0, "lon": 0, "n": 0, "hw": t.get("highway")})
        a["lat"] += c["lat"]
        a["lon"] += c["lon"]
        a["n"] += 1
    out = {
        k: {
            "lat": round(v["lat"] / v["n"], 6),
            "lon": round(v["lon"] / v["n"], 6),
            "hw": v["hw"],
            "segs": v["n"],
        }
        for k, v in agg.items()
    }
    json.dump(out, open("osm_geo.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(sorted(out), open("osm_streets.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("vias nomeadas:", len(out))


def limite():
    d = overpass(
        '[out:json][timeout:120];\n'
        'rel["boundary"="administrative"]["admin_level"="8"]["name"="Cachoeirinha"](%s);\n'
        'out geom;' % BBOX
    )
    segs = []
    for e in d["elements"]:
        for m in e.get("members", []):
            if m.get("type") == "way" and "geometry" in m:
                segs.append([[round(p["lon"], 5), round(p["lat"], 5)] for p in m["geometry"]])
    json.dump(segs, open("boundary.json", "w"))
    print("segmentos de limite:", len(segs))


def geometria():
    """Traçado completo das vias nomeadas — insumo do lines_osm.py."""
    d = overpass(
        '[out:json][timeout:300];\n'
        'rel["boundary"="administrative"]["admin_level"="8"]["name"="Cachoeirinha"](%s);\n'
        'map_to_area->.a;\n'
        '(way(area.a)["highway"]["name"];);\n'
        'out geom;' % BBOX
    )
    json.dump(d, open("_osm_raw_geom.json", "w"))
    print("ways com geometria:", len(d["elements"]))


if __name__ == "__main__":
    ruas()
    limite()
    geometria()
