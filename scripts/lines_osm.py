# -*- coding: utf-8 -*-
"""Converte a geometria bruta do Overpass (_osm_raw_geom.json) em polilinhas
compactas por nome de via -> osm_lines.json  {"linhas":[...], "porNome":{nome:[ids]}}.
Rode de dentro de dados/."""
import json

def simplifica(pts, eps=0.000015):
    """Douglas-Peucker simples, eps em graus (~4 m)."""
    if len(pts) < 3:
        return pts
    def dp(a, b):
        if b - a < 2:
            return []
        x1, y1 = pts[a]; x2, y2 = pts[b]
        dx, dy = x2 - x1, y2 - y1
        n = (dx * dx + dy * dy) ** .5 or 1e-12
        pior, idx = 0, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / n
            if d > pior:
                pior, idx = d, i
        if pior <= eps:
            return []
        return dp(a, idx) + [idx] + dp(idx, b)
    keep = [0] + dp(0, len(pts) - 1) + [len(pts) - 1]
    return [pts[i] for i in sorted(set(keep))]

def main():
    raw = json.load(open('_osm_raw_geom.json', encoding='utf-8'))
    linhas, por_nome = [], {}
    for e in raw['elements']:
        g = e.get('geometry') or []
        nome = e.get('tags', {}).get('name')
        if not nome or len(g) < 2:
            continue
        pts = [[round(p['lon'], 5), round(p['lat'], 5)] for p in g]
        limpo = [pts[0]]
        for p in pts[1:]:
            if p != limpo[-1]:
                limpo.append(p)
        if len(limpo) < 2:
            continue
        limpo = simplifica(limpo)
        por_nome.setdefault(nome, []).append(len(linhas))
        linhas.append(limpo)
    json.dump({'linhas': linhas, 'porNome': por_nome},
              open('osm_lines.json', 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('polilinhas:', len(linhas), 'pontos:', sum(len(l) for l in linhas), 'vias:', len(por_nome))

if __name__ == '__main__':
    main()
