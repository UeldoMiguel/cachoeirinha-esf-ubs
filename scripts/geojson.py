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
FONTE_OFICIAL = ('Lista de contatos das unidades da Secretaria Municipal de Saúde de '
                 'Cachoeirinha/RS')
LONGE_DEMAIS = 1000    # metros: acima disso o ponto do mapa colaborativo não se sustenta
                       # diante do endereço oficial, e o ponto passa a ser o do endereço


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


TELEFONE = re.compile(r'(?<![\d/])(\(?\d{2}\)?[\s.-]*)?(\d{4,5})[\s.-]?(\d{4})(?![\d/])')


def telefone(txt):
    """Primeiro telefone que aparece no texto livre da fonte.

    O texto do KML lista vários setores; o primeiro é o contato principal.
    Datas (12/04/2024) e horários (8h às 17h) não casam com o padrão.
    """
    m = TELEFONE.search(txt or '')
    if not m:
        return None
    ddd = (m.group(1) or '').strip(' .-')
    fixo = m.group(2) + '-' + m.group(3)
    if ddd:
        ddd = ddd.strip('()')
        return '(' + ddd + ') ' + fixo
    return fixo


SETOR_INTERNO = re.compile(r'^(almoxarifado|rh|dp|licitac|compras|financeiro|frota|'
                           r'protocolo|ouvidoria|ti|patrimonio)')


def email(txt):
    """E-mail de atendimento da unidade.

    O texto da Secretaria lista um endereço por setor; os de apoio
    administrativo ficam por último, para não passarem por contato da unidade.
    """
    achados = re.findall(r'[\w.\-+]+@[\w.\-]+\.\w+', txt or '')
    if not achados:
        return None
    externos = [e for e in achados if not SETOR_INTERNO.match(e.lower())]
    return (externos or achados)[0]


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

    # contatos da lista da Secretaria (mandam) e endereços deduzidos do CNEFE
    def carrega(nome_arquivo):
        caminho = os.path.join(RAIZ, 'dados', nome_arquivo)
        return json.load(io.open(caminho, encoding='utf-8')) if os.path.exists(caminho) else {}

    oficiais = carrega('contatos_oficiais.json')
    enderecos = carrega('enderecos_unidades.json')

    def endereco_de(nome):
        o = oficiais.get(nome)
        if o and o.get('endereco'):
            return o['endereco']
        e = enderecos.get(nome)
        if not e:
            return None
        return ' — '.join([e['endereco']] + ([e['bairro']] if e.get('bairro') else []))

    def telefone_de(nome, texto):
        o = oficiais.get(nome)
        if o and o.get('telefone'):
            return o['telefone']
        return telefone(texto)

    def fonte_contato(nome):
        return FONTE_OFICIAL if nome in oficiais else FONTE_AREAS

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
                 'endereco': endereco_de(a['n']),
                 'telefone': telefone_de(a['n'], u.get('info', '')),
                 'email': email(u.get('info', '')),
                 'fonte': FONTE_AREAS}))
        saidas[arquivo] = colecao(
            feats, 'Áreas de ' + tipo + ' — Cachoeirinha/RS', FONTE_AREAS,
            'Limites de trabalho digitalizados em mapa colaborativo. Devem ser '
            'substituídos pelos limites oficiais quando a Secretaria os publicar.')

    feats = []
    for u in unidades:
        info = limpa(u.get('info', ''))
        o = oficiais.get(u['n']) or {}
        ll = [u['ll'][0], u['ll'][1]]
        # ponto absurdamente longe do endereço oficial: vale o endereço
        if o.get('ll') and (o.get('distancia_ponto_m') or 0) > LONGE_DEMAIS:
            print('ponto movido para o endereço oficial:', u['n'],
                  '(%d m)' % o['distancia_ponto_m'])
            ll = o['ll']
        feats.append(feature(
            {'type': 'Point', 'coordinates': [round(ll[1], 6), round(ll[0], 6)]},
            {'nome': u['n'],
             'tipo': u['c'],
             'codigo': codigo(u['n']),
             'tem_area': any(a['n'] == u['n'] for a in areas),
             'endereco': endereco_de(u['n']),
             'telefone': telefone_de(u['n'], info),
             'email': email(info),
             'informacoes': info,
             'fonte': fonte_contato(u['n'])}))

    # unidades que só existem na lista da Secretaria, posicionadas pelo endereço
    nomes_mapa = {u['n'] for u in unidades}
    for nome, o in oficiais.items():
        if nome in nomes_mapa or not o.get('ll'):
            continue
        feats.append(feature(
            {'type': 'Point', 'coordinates': [round(o['ll'][1], 6), round(o['ll'][0], 6)]},
            {'nome': o.get('nome_oficial') or nome,
             'tipo': o.get('tipo') or 'Especialidades',
             'codigo': codigo(o.get('nome_oficial') or nome),
             'tem_area': False,
             'endereco': o['endereco'],
             'telefone': o['telefone'],
             'posicao': 'coordenada do endereço no CNEFE 2022 (' + o['geocodificacao'] + ')',
             'fonte': FONTE_OFICIAL}))
        print('unidade acrescentada da lista oficial:', nome)
    saidas['unidades.geojson'] = colecao(
        feats, 'Unidades e serviços de saúde — Cachoeirinha/RS', FONTE_AREAS,
        'A posição vem do ponto marcado no mapa colaborativo. O endereço, quando '
        'presente, vem do estabelecimento de saúde correspondente no CNEFE 2022 do '
        'IBGE; unidade sem correspondência fica sem endereço.')

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
            'contatos_das_unidades': FONTE_OFICIAL,
        },
        'aviso': ('Dados de trabalho. Os limites territoriais oficiais devem ser '
                  'fornecidos pela Secretaria Municipal de Saúde de Cachoeirinha.'),
    }
    with io.open(os.path.join(destino, 'metadados.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print('metadados.json ok')


if __name__ == '__main__':
    main()
