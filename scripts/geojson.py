# -*- coding: utf-8 -*-
"""Gera os GeoJSON publicados em data/ a partir de dados/final.json.

Saídas (EPSG:4326, como manda a RFC 7946):
  data/esf.geojson       polígonos das áreas de ESF
  data/ubs.geojson       polígonos das áreas de UBS
  data/unidades.geojson  pontos de todas as unidades e serviços
  data/limite.geojson    contorno do município (OpenStreetMap)
  data/metadados.json    procedência, data de geração e contagens

Nada aqui inventa geometria ou atributo: tudo vem do KML do mapa colaborativo
"Mapeamento unidades de saúde — Cachoeirinha" e do OpenStreetMap. Campo que a
fonte não traz simplesmente não entra no arquivo.

Rode da raiz do projeto: python scripts/geojson.py
"""
import datetime
import io
import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTE_AREAS = ('Mapa colaborativo público "Mapeamento unidades de saúde — Cachoeirinha" '
               '(Google My Maps). Dado de trabalho, não é cadastro oficial da Secretaria '
               'Municipal de Saúde.')
FONTE_LIMITE = 'OpenStreetMap, contribuidores (ODbL)'


def codigo(nome):
    """Slug estável para servir de chave do território/unidade."""
    s = unicodedata.normalize('NFD', nome)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()
    s = re.sub(r'[^A-Z0-9]+', '-', s).strip('-')
    return s


def limpa(txt):
    """Texto livre do KML: tira as réguas de '=====' e espaços sobrando."""
    if not txt:
        return ''
    linhas = []
    for ln in txt.replace('\r', '').split('\n'):
        ln = ln.strip()
        if not ln or set(ln) <= set('=-_'):
            continue
        linhas.append(ln)
    return '\n'.join(linhas)


def telefone(txt):
    m = re.search(r'(?:fone|telefone|tel)\.?:?\s*([()\d\s.-]{8,20})', txt or '', re.I)
    return ' '.join(m.group(1).split()) if m else None


def email(txt):
    m = re.search(r'[\w.\-+]+@[\w.\-]+\.\w+', txt or '')
    return m.group(0) if m else None


def feature(geom, props):
    return {'type': 'Feature',
            'properties': {k: v for k, v in props.items() if v not in (None, '', [])},
            'geometry': geom}


def colecao(features, titulo, fonte, observacao=None):
    fc = {'type': 'FeatureCollection',
          'name': titulo,
          'fonte': fonte,
          'gerado_em': datetime.date.today().isoformat(),
          'features': features}
    if observacao:
        fc['observacao'] = observacao
    return fc


def anel_fechado(poly):
    """RFC 7946: o anel externo precisa fechar no primeiro ponto."""
    anel = [[round(p[0], 6), round(p[1], 6)] for p in poly]
    if anel[0] != anel[-1]:
        anel.append(anel[0])
    return anel


def main():
    d = json.load(io.open(os.path.join(RAIZ, 'dados', 'final.json'), encoding='utf-8'))
    areas, unidades = d['areas'], d['unidades']
    por_nome = {u['n']: u for u in unidades}

    saidas = {}
    for tipo, arquivo in (('ESF', 'esf.geojson'), ('UBS', 'ubs.geojson')):
        feats = []
        for a in areas:
            if a['t'] != tipo:
                continue
            u = por_nome.get(a['n'], {})
            feats.append(feature(
                {'type': 'Polygon', 'coordinates': [anel_fechado(a['poly'])]},
                {'nome': 'Área da ' + a['n'],
                 'unidade': a['n'],
                 'tipo': tipo,
                 'codigo': codigo(a['n']),
                 'descricao': ('Território de abrangência da ' + a['n'] + ', com ' +
                               str(len(a['ruas'])) + ' vias na lista de ruas da fonte.'),
                 'ruas_cadastradas': len(a['ruas']),
                 'ruas': sorted(a['ruas']),
                 'telefone': telefone(u.get('info', '')),
                 'email': email(u.get('info', '')),
                 'fonte': FONTE_AREAS}))
        saidas[arquivo] = colecao(
            feats, 'Áreas de ' + tipo + ' — Cachoeirinha/RS', FONTE_AREAS,
            'Limites de trabalho digitalizados em mapa colaborativo. Devem ser '
            'substituídos pelos limites oficiais quando a Secretaria os publicar.')

    feats = []
    for u in unidades:
        info = limpa(u.get('info', ''))
        feats.append(feature(
            {'type': 'Point', 'coordinates': [round(u['ll'][1], 6), round(u['ll'][0], 6)]},
            {'nome': u['n'],
             'tipo': u['c'],
             'codigo': codigo(u['n']),
             'tem_area': any(a['n'] == u['n'] for a in areas),
             'telefone': telefone(info),
             'email': email(info),
             'informacoes': info,
             'fonte': FONTE_AREAS}))
    saidas['unidades.geojson'] = colecao(
        feats, 'Unidades e serviços de saúde — Cachoeirinha/RS', FONTE_AREAS,
        'Endereço postal não consta na fonte; a posição vem do ponto marcado no mapa.')

    bound = d.get('bound') or []
    saidas['limite.geojson'] = colecao(
        [feature({'type': 'MultiLineString',
                  'coordinates': [[[round(p[0], 6), round(p[1], 6)] for p in seg]
                                  for seg in bound]},
                 {'nome': 'Limite do município de Cachoeirinha/RS',
                  'codigo': 'LIMITE-CACHOEIRINHA',
                  'fonte': FONTE_LIMITE})],
        'Limite municipal — Cachoeirinha/RS', FONTE_LIMITE)

    destino = os.path.join(RAIZ, 'data')
    os.makedirs(destino, exist_ok=True)
    for arquivo, fc in saidas.items():
        with io.open(os.path.join(destino, arquivo), 'w', encoding='utf-8') as f:
            json.dump(fc, f, ensure_ascii=False, indent=1)
        print(arquivo, len(fc['features']), 'feições,',
              os.path.getsize(os.path.join(destino, arquivo)), 'bytes')

    meta = {
        'municipio': 'Cachoeirinha/RS',
        'codigo_ibge': '4303103',
        'gerado_em': datetime.date.today().isoformat(),
        'camadas': {
            'esf.geojson': sum(1 for a in areas if a['t'] == 'ESF'),
            'ubs.geojson': sum(1 for a in areas if a['t'] == 'UBS'),
            'unidades.geojson': len(unidades),
            'limite.geojson': 1,
        },
        'fontes': {
            'areas_e_unidades': FONTE_AREAS,
            'limite_municipal': FONTE_LIMITE,
        },
        'aviso': ('Dados de trabalho. Os limites territoriais oficiais devem ser '
                  'fornecidos pela Secretaria Municipal de Saúde de Cachoeirinha.'),
    }
    with io.open(os.path.join(destino, 'metadados.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print('metadados.json ok')


if __name__ == '__main__':
    main()
