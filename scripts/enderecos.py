# -*- coding: utf-8 -*-
"""Casa cada unidade de saúde com o endereço dela no CNEFE 2022 do IBGE.

O mapa colaborativo traz só o ponto da unidade, sem endereço postal. O CNEFE
cadastra os estabelecimentos de saúde (espécie 5) com logradouro, número e
coordenada — então o endereço vem de fonte oficial, não de suposição.

Critério, em duas passadas:
  1. nome: o estabelecimento cujo nome compartilha token distintivo com o da
     unidade (um token até 400 m, dois ou mais até 2 km);
  2. proximidade: para quem sobrou, o equipamento público mais próximo dentro
     de 60 m que nenhuma outra unidade já reivindicou.
Cada registro do CNEFE é usado uma vez só. Sem candidato, a unidade fica sem
endereço — nada é inventado.

Saída: dados/enderecos_unidades.json
  {"UBS COHAB": {"endereco": "...", "bairro": "...", "cep": "...",
                 "estabelecimento": "...", "distancia_m": 9}}

Rode de dentro de dados/: python ../scripts/enderecos.py
"""
import csv
import io
import json
import math
import re
import unicodedata
import zipfile

RAIO_PROXIMO = 80          # metros: colado no ponto da unidade
RAIO_NOME = 400            # metros: um token distintivo em comum basta
RAIO_NOME_LONGE = 2000     # metros: dois ou mais tokens em comum
PUBLICO = re.compile(r'(?:POSTO|UBS|UNIDADE BASICA|UNIDADE DE|CAPS|UPA|HOSPITAL|'
                     r'SECRETARIA|CENTRO DE SAUDE|PRONTO ATENDIMENTO|AMBULATORIO)')
PALAVRAS_VAGAS = {'posto', 'saude', 'unidade', 'basica', 'municipal', 'de', 'da', 'do',
                  'centro', 'publico', 'horas', 'municipio', 'atendimento', 'pronto'}


def sem_acento(s):
    s = unicodedata.normalize('NFD', str(s or ''))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()


def tokens(nome):
    t = re.sub(r'[^A-Z0-9 ]', ' ', sem_acento(nome)).split()
    return {x for x in t if len(x) > 2 and x.lower() not in PALAVRAS_VAGAS}


def publico(nome):
    """Distingue equipamento público de clínica ou consultório particular."""
    return bool(PUBLICO.search(sem_acento(nome)))


def metros(a, b):
    return math.hypot((a[1] - b[1]) * math.cos(math.radians(a[0])) * 111320,
                      (a[0] - b[0]) * 111320)


MINUSCULAS = {'Da', 'De', 'Do', 'Das', 'Dos', 'E'}
ROMANOS = {'Ii', 'Iii', 'Iv', 'Vi', 'Vii', 'Viii', 'Ix', 'Xi', 'Xii', 'Xiii', 'Xxiii'}


def arruma_caixa(nome):
    partes = []
    for i, w in enumerate(nome.title().split()):
        if w in ROMANOS:
            partes.append(w.upper())
        elif i and w in MINUSCULAS:
            partes.append(w.lower())
        else:
            partes.append(w)
    return ' '.join(partes)


def carrega_grafia():
    """Grafia com acento das vias, vinda do OpenStreetMap, para o CNEFE — que
    guarda tudo sem acento — sair legível: SAO JORGE -> São Jorge."""
    try:
        nomes = json.load(io.open('osm_streets.json', encoding='utf-8'))
    except (IOError, OSError, ValueError):
        return {}
    return {re.sub(r'\s+', ' ', sem_acento(n)).strip(): n for n in nomes}


GRAFIA = {}


def formata(row):
    via = ' '.join(x for x in (row['NOM_TIPO_SEGLOGR'], row['NOM_TITULO_SEGLOGR'],
                               row['NOM_SEGLOGR']) if x).strip()
    via = GRAFIA.get(re.sub(r'\s+', ' ', sem_acento(via)).strip()) or arruma_caixa(via)
    try:
        num = int(row['NUM_ENDERECO'])
    except (TypeError, ValueError):
        num = 0
    return via + (', ' + str(num) if num > 0 else ', s/n')


def main():
    global GRAFIA
    GRAFIA = carrega_grafia()
    print('grafias com acento vindas do OSM:', len(GRAFIA))
    z = zipfile.ZipFile('cnefe.zip')
    saude = []
    with z.open(z.namelist()[0]) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding='latin-1'), delimiter=';'):
            if row['COD_ESPECIE'] != '5':          # 5 = estabelecimento de saúde
                continue
            try:
                ll = (float(row['LATITUDE']), float(row['LONGITUDE']))
            except (TypeError, ValueError):
                continue
            saude.append({
                'll': ll,
                'estab': row['DSC_ESTABELECIMENTO'].strip(),
                'endereco': formata(row),
                'bairro': arruma_caixa(row['DSC_LOCALIDADE'].strip()),
                'cep': row['CEP'].strip(),
            })
    print('estabelecimentos de saúde no CNEFE:', len(saude))

    unidades = json.load(io.open('final.json', encoding='utf-8'))['unidades']
    saida, sem = {}, []
    usados = set()

    def registra(nome, e, d, por_nome):
        usados.add(id(e))
        saida[nome] = {
            'endereco': e['endereco'],
            'bairro': e['bairro'],
            'cep': e['cep'],
            'estabelecimento': e['estab'],
            'distancia_m': round(d),
            'por_nome': por_nome,
        }

    # 1ª passada: casamento por nome. Um token distintivo basta se estiver perto;
    # de longe, exige dois — "Pessoa Idosa", "Carlos Wilkens", "Jardim do Bosque".
    candidatos = []
    for u in unidades:
        ll = (u['ll'][0], u['ll'][1])
        alvo = tokens(u['n'])
        for e in saude:
            comuns = alvo & tokens(e['estab'])
            if not comuns:
                continue
            d = metros(ll, e['ll'])
            if d <= RAIO_NOME or (len(comuns) >= 2 and d <= RAIO_NOME_LONGE):
                candidatos.append((len(comuns) * -1, d, u['n'], e))
    candidatos.sort(key=lambda c: (c[0], c[1]))     # mais tokens em comum, depois mais perto
    for _, d, nome, e in candidatos:
        if nome in saida or id(e) in usados:
            continue
        registra(nome, e, d, True)

    # 2ª passada: unidade pública ainda sem endereço pega o estabelecimento
    # público mais próximo que ninguém reivindicou, e só se estiver colado.
    for u in unidades:
        if u['n'] in saida:
            continue
        ll = (u['ll'][0], u['ll'][1])
        melhor, melhor_d = None, 1e9
        for e in saude:
            if id(e) in usados or not publico(e['estab']):
                continue
            d = metros(ll, e['ll'])
            if d <= RAIO_PROXIMO and d < melhor_d:
                melhor, melhor_d = e, d
        if melhor:
            registra(u['n'], melhor, melhor_d, False)
        else:
            sem.append(u['n'])

    json.dump(saida, io.open('enderecos_unidades.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('com endereço:', len(saida), 'de', len(unidades))
    for nome, e in sorted(saida.items()):
        print('  %-52s %-46s %3dm %s' % (nome[:52], e['endereco'][:46], e['distancia_m'],
                                         'nome' if e['por_nome'] else 'proximidade'))
    if sem:
        print('sem endereço:', '; '.join(sem))


if __name__ == '__main__':
    main()
