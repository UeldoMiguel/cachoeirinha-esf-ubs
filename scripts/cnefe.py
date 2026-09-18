# -*- coding: utf-8 -*-
"""Lê o CNEFE 2022 de Cachoeirinha (IBGE) e resume cada face de quadra.

Entrada : cnefe.zip (baixado por baixar_cnefe(), ~1,4 MB)
Saída   : trechos.json  {"porRua": {chave: [[numMin, numMax, [[lon,lat],...], qtd], ...]}}

Uma "face" no CNEFE é o lado de quadra de um logradouro: é o trecho que a
consulta marca em vermelho quando a pessoa digita o número da casa. A polilinha
de cada face é traçada pelos próprios endereços, ordenados ao longo da direção
principal da nuvem de pontos.

Rode de dentro de dados/: python ../scripts/cnefe.py
"""
import collections
import csv
import io
import json
import os
import urllib.request
import zipfile

URL = ('https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/'
       'Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/43_RS/4303103_CACHOEIRINHA.zip')


def baixar_cnefe(destino='cnefe.zip'):
    if os.path.exists(destino):
        print('cnefe.zip já está aqui')
        return destino
    req = urllib.request.Request(URL, headers={'User-Agent': 'health-map/1.0'})
    with urllib.request.urlopen(req, timeout=300) as r, open(destino, 'wb') as f:
        f.write(r.read())
    print('baixado:', os.path.getsize(destino), 'bytes')
    return destino


def ler_faces(zip_path='cnefe.zip'):
    z = zipfile.ZipFile(zip_path)
    nome_csv = z.namelist()[0]
    faces = collections.defaultdict(list)
    with z.open(nome_csv) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding='latin-1'), delimiter=';'):
            try:
                num = int(row['NUM_ENDERECO'])
            except (TypeError, ValueError):
                continue
            if num <= 0:                      # 0 no CNEFE significa "sem número"
                continue
            logr = ' '.join(x for x in (row['NOM_TIPO_SEGLOGR'],
                                        row['NOM_TITULO_SEGLOGR'],
                                        row['NOM_SEGLOGR']) if x).strip()
            chave = (logr, row['COD_SETOR'], row['NUM_QUADRA'], row['NUM_FACE'])
            faces[chave].append((num, float(row['LATITUDE']), float(row['LONGITUDE'])))
    return faces


def polilinha(pontos):
    """Ordena os endereços pela direção principal e devolve 2–4 pontos."""
    xs = [p[2] for p in pontos]
    ys = [p[1] for p in pontos]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    # autovetor dominante da matriz de covariância 2x2
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    lam = tr / 2 + ((tr * tr) / 4 - det) ** .5 if (tr * tr) / 4 - det > 0 else tr / 2
    if abs(sxy) > 1e-12:
        vx, vy = lam - syy, sxy
    else:
        vx, vy = (1, 0) if sxx >= syy else (0, 1)
    n = (vx * vx + vy * vy) ** .5 or 1
    vx, vy = vx / n, vy / n
    ordenados = sorted(pontos, key=lambda p: (p[2] - mx) * vx + (p[1] - my) * vy)
    if len(ordenados) <= 2:
        pts = ordenados
    else:  # extremos + um ponto do meio segura a curvatura da rua
        pts = [ordenados[0], ordenados[len(ordenados) // 2], ordenados[-1]]
    saida = []
    for _, lat, lon in pts:
        p = [round(lon, 5), round(lat, 5)]
        if not saida or p != saida[-1]:
            saida.append(p)
    return saida


def main():
    baixar_cnefe()
    faces = ler_faces()
    por_rua = collections.defaultdict(list)
    descartadas = 0
    for (logr, _setor, _quadra, _face), pts in faces.items():
        linha = polilinha(pts)
        if len(linha) < 2:                      # face com um endereço só: vira ponto duplicado
            linha = [linha[0], linha[0]] if linha else None
        if not linha:
            descartadas += 1
            continue
        nums = [p[0] for p in pts]
        por_rua[logr].append([min(nums), max(nums), linha, len(pts)])
    for v in por_rua.values():
        v.sort(key=lambda t: t[0])
    saida = {'porRua': por_rua}
    json.dump(saida, open('trechos.json', 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('logradouros:', len(por_rua),
          '| trechos:', sum(len(v) for v in por_rua.values()),
          '| descartados:', descartadas,
          '| bytes:', os.path.getsize('trechos.json'))


if __name__ == '__main__':
    main()
