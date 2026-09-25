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
import json as _json
import math
import json
import os
import re
import unicodedata

from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union


def shapely_json(geom):
    return _json.dumps(mapping(geom))


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

    # linhas sem WhatsApp: o número aparece igual, só não vira link
    sem_link = (carrega('whatsapp.json') or {}).get('sem_link', {})

    def sem_whatsapp(nome):
        v = sem_link.get(nome)
        if v is None:
            return None
        return True if v == 'todos' else list(v)

    destaques = carrega('destaques.json')
    cor_destaque = {}
    for cor in ('vermelho', 'amarelo', 'azul'):
        for nome in destaques.get(cor, []):
            cor_destaque[nome] = cor

    oficiais = carrega('contatos_oficiais.json')
    enderecos = carrega('enderecos_unidades.json')
    # final.json já traz o nome renomeado; a busca aceita os dois
    for chave, reg in list(oficiais.items()):
        if reg.get('renomear'):
            oficiais.setdefault(reg['renomear'], reg)

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

    def email_de(nome, texto, outro=None):
        """E-mail da lista da Secretaria; '' na lista significa "não tem".

        A unidade pode ser procurada pelo nome do mapa ou pelo nome de
        exibição: a lista responde pelos dois.
        """
        for n in (nome, outro):
            o = oficiais.get(n) if n else None
            if o and 'email' in o:
                return o['email'] or None
        return email(texto)

    def fonte_contato(nome):
        return FONTE_OFICIAL if nome in oficiais else FONTE_AREAS

    def nome_de(nome):
        """Nome de exibição: a lista da Secretaria pode renomear o que veio do mapa."""
        o = oficiais.get(nome) or {}
        return o.get('renomear') or nome

    def props_area(a, u):
        return {'nome': 'Área da ' + a['n'],
             'unidade': a['n'],
             'tipo': a['t'],
             'codigo': codigo(a['n']),
             'codigos': [codigo(a['n'])],
             'descricao': ('Território de abrangência da ' + a['n'] + ', com ' +
                           str(len(a['ruas'])) + ' vias na lista de ruas da fonte.'),
             'ruas_cadastradas': len(a['ruas']),
             'ruas': sorted(a['ruas']),
             'endereco': endereco_de(a['n']),
             'telefone': telefone_de(a['n'], u.get('info', '')),
             'sem_whatsapp': sem_whatsapp(a['n']),
             'email': email_de(a['n'], u.get('info', '')),
             'fonte': FONTE_AREAS}

    def area_unida(grupo):
        """Funde as áreas de um grupo de UBS numa feição só."""
        membros = [a for a in areas if a['n'] in grupo]
        if len(membros) < 2:
            return None
        pecas = [Polygon(anel_fechado(a['poly'])).buffer(0) for a in membros]
        soltas = [Polygon(anel_fechado(r)).buffer(0)
                  for a in membros for r in a.get('poly_extra') or []]
        juntas = unary_union(pecas)
        # as áreas vizinhas foram digitalizadas com folga de 12 a 31 m entre si;
        # fechar 25 m dissolve a divisa interna sem inchar o território (+0,4%)
        juntas = juntas.buffer(25 / 111320.0).buffer(-25 / 111320.0)
        juntas = juntas.simplify(3 / 111320.0)                       # tira vértices do arredondamento
        if soltas:
            # o território herdado de outra unidade não encosta no resto: entra
            # como parte separada do mesmo desenho, sem ser unido a ele
            juntas = unary_union([juntas] + soltas)
        nomes = [a['n'] for a in membros]
        rotulo = (', '.join(nomes[:-1]) + ' e ' + nomes[-1]) if len(nomes) > 1 else nomes[0]
        ruas = sorted({r for a in membros for r in a['ruas']})
        return feature(json.loads(shapely_json(juntas)), {
            'nome': 'Área da ' + rotulo,
            'unidade': rotulo,
            'tipo': 'UBS',
            'codigo': codigo(rotulo),
            'codigos': [codigo(n) for n in nomes],
            'descricao': 'Território atendido em conjunto por ' + rotulo + '.',
            'ruas_cadastradas': len(ruas),
            'ruas': ruas,
            'unidades': [{'nome': n,
                          'endereco': endereco_de(n),
                          'telefone': telefone_de(n, (por_nome.get(n) or {}).get('info', '')),
                          'sem_whatsapp': sem_whatsapp(n)}
                         for n in nomes],
            'fonte': FONTE_AREAS})

    def colecao_areas(tipo, grupos, titulo):
        feats, agrupadas = [], set()
        for grupo in grupos:
            f = area_unida(grupo)
            if not f:
                continue
            feats.append(f)
            agrupadas.update(grupo)
            print('áreas unidas (%s): %s' % (titulo, ' + '.join(grupo)))
        for a in areas:
            if a['t'] != tipo or a['n'] in agrupadas:
                continue
            extras = a.get('poly_extra') or []
            if extras:
                # um território que a unidade herdou, longe da área principal:
                # MultiPolygon mantém as partes separadas, cada uma no seu lugar
                geom = {'type': 'MultiPolygon',
                        'coordinates': [[anel_fechado(a['poly'])]] +
                                       [[anel_fechado(r)] for r in extras]}
            else:
                geom = {'type': 'Polygon', 'coordinates': [anel_fechado(a['poly'])]}
            feats.append(feature(geom, props_area(a, por_nome.get(a['n'], {}))))
        return colecao(feats, 'Áreas de ' + tipo + ' — Cachoeirinha/RS', FONTE_AREAS,
                       'Limites de trabalho digitalizados em mapa colaborativo. Devem ser '
                       'substituídos pelos limites oficiais quando a Secretaria os publicar.')

    saidas = {}
    grupos = carrega('agrupamentos_ubs.json')
    saidas['esf.geojson'] = colecao_areas('ESF', [], 'ESF')
    saidas['ubs.geojson'] = colecao_areas('UBS', grupos.get('medico', []), 'médico/enfermeiro')
    saidas['ubs_odonto.geojson'] = colecao_areas('UBS', grupos.get('dentista', []), 'dentista')

    feats = []
    for u in unidades:
        info = limpa(u.get('info', ''))
        o = oficiais.get(u['n']) or {}
        ll = [u['ll'][0], u['ll'][1]]
        # ponto vai para o endereço oficial quando a lista pede, ou quando o
        # alfinete do mapa colaborativo está longe demais para se sustentar
        if o.get('ll') and (o.get('usar_coordenada_do_endereco')
                            or (o.get('distancia_ponto_m') or 0) > LONGE_DEMAIS):
            print('ponto movido para o endereço oficial:', u['n'],
                  '(%d m)' % (o.get('distancia_ponto_m') or 0))
            ll = o['ll']
        feats.append(feature(
            {'type': 'Point', 'coordinates': [round(ll[1], 6), round(ll[0], 6)]},
            {'nome': nome_de(u['n']),
             'tipo': u['c'],
             'codigo': codigo(nome_de(u['n'])),
             'tem_area': any(a['n'] == u['n'] for a in areas),
             'endereco': endereco_de(u['n']),
             'telefone': telefone_de(u['n'], info),
             'sem_whatsapp': sem_whatsapp(nome_de(u['n'])) or sem_whatsapp(u['n']),
             'email': email_de(nome_de(u['n']), info, u['n']),
             'destaque': cor_destaque.get(nome_de(u['n'])) or cor_destaque.get(u['n']),
             'informacoes': info,
             'fonte': fonte_contato(u['n'])}))

    # unidades que só existem na lista da Secretaria, posicionadas pelo endereço
    nomes_mapa = {u['n'] for u in unidades}
    ja_vistos = set()
    for nome, o in oficiais.items():
        renomeado = o.get('renomear')
        if (nome in nomes_mapa or (renomeado and renomeado in nomes_mapa)
                or id(o) in ja_vistos or not o.get('ll')):
            continue
        ja_vistos.add(id(o))
        feats.append(feature(
            {'type': 'Point', 'coordinates': [round(o['ll'][1], 6), round(o['ll'][0], 6)]},
            {'nome': o.get('nome_oficial') or nome,
             'tipo': o.get('tipo') or 'Especialidades',
             'codigo': codigo(o.get('nome_oficial') or nome),
             'tem_area': False,
             'endereco': o['endereco'],
             'telefone': o['telefone'],
             'sem_whatsapp': sem_whatsapp(o.get('nome_oficial') or nome),
             'destaque': cor_destaque.get(o.get('nome_oficial') or nome),
             'posicao': 'coordenada do endereço no CNEFE 2022 (' + o['geocodificacao'] + ')',
             'fonte': FONTE_OFICIAL}))
        print('unidade acrescentada da lista oficial:', nome)
    saidas['unidades.geojson'] = colecao(
        feats, 'Unidades e serviços de saúde — Cachoeirinha/RS', FONTE_AREAS,
        'A posição vem do ponto marcado no mapa colaborativo. O endereço, quando '
        'presente, vem do estabelecimento de saúde correspondente no CNEFE 2022 do '
        'IBGE; unidade sem correspondência fica sem endereço.')

    # unidades no mesmo endereço ficariam empilhadas e só a de cima receberia o
    # clique: abre-se um leque de 15 m em torno do ponto comum
    grupos = {}
    for f in feats:
        chave = tuple(round(c, 5) for c in f['geometry']['coordinates'])
        grupos.setdefault(chave, []).append(f)
    for chave, juntas in grupos.items():
        if len(juntas) < 2:
            continue
        lon0, lat0 = chave
        raio = 15.0 / 111320.0
        print('mesmo endereço, pontos afastados em leque:',
              ', '.join(f['properties']['nome'] for f in juntas))
        for i, f in enumerate(juntas):
            ang = 2 * math.pi * i / len(juntas)
            f['geometry']['coordinates'] = [
                round(lon0 + raio * math.cos(ang) / math.cos(math.radians(lat0)), 6),
                round(lat0 + raio * math.sin(ang), 6)]
            f['properties']['posicao'] = (f['properties'].get('posicao') or
                                          'coordenada do endereço') +                 ' · deslocada 15 m para não cobrir outra unidade no mesmo endereço'

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
