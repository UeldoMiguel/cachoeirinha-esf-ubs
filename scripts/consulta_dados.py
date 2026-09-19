# -*- coding: utf-8 -*-
"""Gera data/consulta.json: o que a busca por endereço precisa no mapa.

Formato (compacto de propósito — o arquivo é baixado pelo navegador):

{
  "ruas":   [[chave, rotulo, [codigoArea, ...], lat, lon, sugerida, [idLinha, ...]], ...],
  "linhas": [[[lon, lat], ...], ...],          traçados do OpenStreetMap
  "trechos": {chave: [[numMin, numMax, [[lon, lat], ...], qtdEnderecos], ...]}
}

`chave` é o nome da via normalizado (sem acento, sem tipo de logradouro, sem
abreviatura). `codigoArea` é o mesmo slug usado nos GeoJSON, então a página
liga a rua ao polígono sem depender de índice posicional.

Rode da raiz do projeto: python scripts/consulta_dados.py
"""
import io
import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def codigo(nome):
    s = unicodedata.normalize('NFD', nome)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()
    return re.sub(r'[^A-Z0-9]+', '-', s).strip('-')


def main():
    d = json.load(io.open(os.path.join(RAIZ, 'dados', 'final.json'), encoding='utf-8'))
    areas = d['areas']
    cod_da_area = [codigo(a['n']) for a in areas]

    ruas = []
    for e in d['idx']:
        chave, rotulo, indices = e[0], e[1], e[2]
        lat, lon, prov = e[3], e[4], e[5]
        linhas = e[6]
        ruas.append([chave, rotulo, [cod_da_area[i] for i in indices],
                     lat, lon, prov, linhas])

    saida = {'ruas': ruas, 'linhas': d['linhas'], 'trechos': d['trechos']}
    destino = os.path.join(RAIZ, 'data', 'consulta.json')
    with io.open(destino, 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, separators=(',', ':'))

    print('ruas:', len(ruas),
          '| com traçado:', sum(1 for r in ruas if r[6]),
          '| com numeração:', sum(1 for r in ruas if r[0] in saida['trechos']),
          '| polilinhas:', len(saida['linhas']),
          '| bytes:', os.path.getsize(destino))


if __name__ == '__main__':
    main()
