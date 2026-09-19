# -*- coding: utf-8 -*-
"""Confere a lista oficial de contatos das unidades e geocodifica os endereços.

Entrada : dados/unidades_oficiais.json  (lista da Secretaria, transcrita)
          dados/cnefe.zip               (para achar a coordenada do endereço)
          dados/final.json              (pontos do mapa colaborativo)
Saída   : dados/contatos_oficiais.json
          {nome_no_mapa | nome_oficial: {telefone, endereco, ll, geocodificado,
                                         distancia_ponto_m, novo}}

O endereço da lista manda. A coordenada só é usada para as unidades que não
existiam no mapa (eMulti, SAE - Tuberculose, SAM) e para medir a distância
entre o ponto desenhado no mapa colaborativo e o endereço informado — quando a
diferença é grande, o relatório avisa, mas nada é movido sem decisão humana.

Rode de dentro de dados/: python ../scripts/oficial.py
"""
import csv
import io
import json
import math
import re
import unicodedata
import zipfile


def sem_acento(s):
    s = unicodedata.normalize('NFD', str(s or ''))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()


TIPOS_VIA = ('RUA', 'AVENIDA', 'AV', 'TRAVESSA', 'TV', 'BECO', 'ESTRADA', 'PRACA',
             'ALAMEDA', 'RODOVIA', 'LARGO', 'VIELA', 'ACESSO', 'PASSAGEM')
ABREV = {'DOM': 'DOM', 'D': 'DOM', 'GEN': 'GENERAL', 'GAL': 'GENERAL', 'CEL': 'CORONEL',
         'DR': 'DOUTOR', 'PE': 'PADRE', 'PROF': 'PROFESSOR', 'CAP': 'CAPITAO',
         'STO': 'SANTO', 'STA': 'SANTA', 'S': 'SAO'}
IGNORA = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E'}


def chave_via(nome):
    """Chave tolerante: sem acento, sem tipo de via, sem abreviatura, sem conectivo."""
    t = re.sub(r'[^A-Z0-9 ]', ' ', sem_acento(nome)).split()
    if t and t[0] in TIPOS_VIA:
        t = t[1:]
    t = [ABREV.get(x, x) for x in t if x not in IGNORA]
    return ' '.join(t)


def numero(endereco):
    m = re.search(r',\s*(\d{1,6})\s*$', endereco or '')
    return int(m.group(1)) if m else None


NUMERO_TEL = re.compile(r'(?<![\d)])(\d{4,5})[\s.-]?(\d{4})(?!\d)')


def com_ddd(texto):
    """Põe (51) em cada número da lista, preservando as observações de ramal."""
    def troca(m):
        return '(51) ' + m.group(1) + '-' + m.group(2)
    return NUMERO_TEL.sub(troca, texto or '')


def metros(a, b):
    return math.hypot((a[1] - b[1]) * math.cos(math.radians(a[0])) * 111320,
                      (a[0] - b[0]) * 111320)


def carrega_cnefe(zip_path='cnefe.zip'):
    """Endereços do CNEFE indexados por (chave da via, número)."""
    por_via = {}
    z = zipfile.ZipFile(zip_path)
    with z.open(z.namelist()[0]) as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding='latin-1'), delimiter=';'):
            try:
                lat, lon = float(row['LATITUDE']), float(row['LONGITUDE'])
                num = int(row['NUM_ENDERECO'])
            except (TypeError, ValueError):
                continue
            via = ' '.join(x for x in (row['NOM_TIPO_SEGLOGR'], row['NOM_TITULO_SEGLOGR'],
                                       row['NOM_SEGLOGR']) if x)
            por_via.setdefault(chave_via(via), []).append((num, lat, lon))
    return por_via


def acha_via(chave, por_via):
    """A lista da Secretaria abrevia e às vezes troca uma letra; o CNEFE escreve
    por extenso. Sem casamento exato, vale o nome que compartilha mais palavras."""
    if chave in por_via:
        return por_via[chave], 'exata'
    alvo = set(chave.split())
    if not alvo:
        return None, None
    melhor, nota, nome = None, 0, None
    for k, v in por_via.items():
        comuns = alvo & set(k.split())
        if len(comuns) < max(1, len(alvo) - 1):
            continue
        pontos = len(comuns) - abs(len(k.split()) - len(alvo)) * .1
        if pontos > nota:
            melhor, nota, nome = v, pontos, k
    if melhor and nota >= 2:
        return melhor, 'via aproximada (%s)' % nome.title()
    return None, None


def geocodifica(endereco, por_via):
    """Coordenada do endereço: número exato, senão o número mais próximo da via."""
    via = chave_via(re.sub(r',.*$', '', endereco or ''))
    lista, como_via = acha_via(via, por_via)
    if not lista:
        return None, 'via não encontrada no CNEFE'
    sufixo = '' if como_via == 'exata' else ' · ' + como_via
    num = numero(endereco)
    if num is None:
        lat = sum(x[1] for x in lista) / len(lista)
        lon = sum(x[2] for x in lista) / len(lista)
        return [round(lat, 6), round(lon, 6)], 'via inteira, endereço sem número' + sufixo
    exatos = [x for x in lista if x[0] == num]
    if exatos:
        return [round(exatos[0][1], 6), round(exatos[0][2], 6)], 'número exato' + sufixo
    perto = min(lista, key=lambda x: abs(x[0] - num))
    return ([round(perto[1], 6), round(perto[2], 6)],
            'número mais próximo (%d)' % perto[0] + sufixo)


def main():
    oficial = json.load(io.open('unidades_oficiais.json', encoding='utf-8'))
    unidades = json.load(io.open('final.json', encoding='utf-8'))['unidades']
    por_nome = {u['n']: u for u in unidades}
    por_via = carrega_cnefe()
    print('vias no CNEFE:', len(por_via))

    saida = {}
    for item in oficial['unidades']:
        alvo = item.get('alias') or item['nome_oficial']
        ll, como = geocodifica(item['endereco'], por_via)
        registro = {
            'nome_oficial': item['nome_oficial'],
            'telefone': com_ddd(item['telefone']),
            'endereco': item['endereco'],
            'geocodificacao': como,
            'll': ll,
            'novo': alvo not in por_nome,
        }
        if not registro['novo'] and ll:
            u = por_nome[alvo]
            registro['distancia_ponto_m'] = round(metros((u['ll'][0], u['ll'][1]), (ll[0], ll[1])))
        if item.get('tipo'):
            registro['tipo'] = item['tipo']
        if item.get('usar_coordenada_do_endereco'):
            registro['usar_coordenada_do_endereco'] = True
        saida[alvo] = registro

    json.dump(saida, io.open('contatos_oficiais.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('unidades na lista oficial:', len(saida))
    print('%-46s %-38s %-26s %s' % ('UNIDADE', 'ENDEREÇO', 'GEOCODIFICAÇÃO', 'DIST. DO PONTO'))
    for nome, r in saida.items():
        print('%-46s %-38s %-26s %s' % (
            nome[:46], r['endereco'][:38], r['geocodificacao'][:26],
            'nova unidade' if r['novo'] else
            ('%d m' % r['distancia_ponto_m'] if r.get('distancia_ponto_m') is not None else '—')))

    faltando = [u['n'] for u in unidades if u['n'] not in saida]
    if faltando:
        print('sem contato na lista oficial:', '; '.join(faltando))


if __name__ == '__main__':
    main()
