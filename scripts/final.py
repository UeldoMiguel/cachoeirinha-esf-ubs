import os
import json,re
d=json.load(open('app_data.json',encoding='utf-8'))
geo=json.load(open('osm_geo.json',encoding='utf-8'))
lin=json.load(open('osm_lines.json',encoding='utf-8'))
tre=json.load(open('trechos.json',encoding='utf-8'))['porRua']
import importlib.util
spec=importlib.util.spec_from_file_location('b','build.py')
# reuse norm by re-exec of just the function block
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'build.py'),encoding='utf-8').read()
ns={'re':re,'unicodedata':__import__('unicodedata')}
exec(src[src.index('def strip_acc'):src.index('def parse_streets')],ns)
norm=ns['norm']
geon={}
for k,v in geo.items():
    geon.setdefault(norm(k),v)
# traçados por chave normalizada (uma via pode ter vários segmentos)
linn={}
for nome,ids in lin['porNome'].items():
    linn.setdefault(norm(nome),[]).extend(ids)

# casamento tolerante: o mapa oficial abrevia nomes que o OSM escreve por extenso
def sem_iniciais(k):
    return tuple(t for t in k.split() if len(t)>1)
por_tokens={}
for k in linn:
    por_tokens.setdefault(sem_iniciais(k),[]).append(k)
extra=[0,0]
def tracado(k):
    if k in linn: return linn[k]
    t=sem_iniciais(k)
    if not t: return []
    if t in por_tokens and len(por_tokens[t])==1:
        extra[0]+=1; return linn[por_tokens[t][0]]
    st=set(t)
    cands=[c for c in por_tokens if st and st.issubset(set(c))]   # abreviado ⊂ por extenso
    if len(cands)==1 and len(por_tokens[cands[0]])==1:
        extra[1]+=1; return linn[por_tokens[cands[0]][0]]
    return []                                                     # ambíguo: não desenha nada
# --- limite do município: recorta as áreas e descarta o que cai fora dele ----
from shapely.geometry import Polygon, Point, shape
from shapely.ops import linemerge, polygonize, unary_union

def municipio():
    segs=json.load(open('boundary.json'))
    partes=list(polygonize(linemerge([[(x,y) for x,y in seg] for seg in segs])))
    if not partes:
        raise SystemExit('não foi possível fechar o limite municipal a partir de boundary.json')
    return unary_union(partes)

LIMITE=municipio()
print('limite municipal: %.2f km2' % (LIMITE.area*111.32*111.32*0.87))

def recorta(poly):
    """Interseção da área com o município. Devolve o anel do maior pedaço."""
    p=Polygon([(x,y) for x,y in poly])
    if not p.is_valid:
        p=p.buffer(0)
    corte=p.intersection(LIMITE)
    if corte.is_empty:
        return None,0.0
    if corte.geom_type=='MultiPolygon':
        maior=max(corte.geoms,key=lambda g:g.area)
    else:
        maior=corte
    perdido=1-(corte.area/p.area) if p.area else 0
    return [[round(x,5),round(y,5)] for x,y in maior.exterior.coords], perdido

# recortes manuais pedidos pela Secretaria (dados/recortes_areas.json)
from shapely.geometry import box as _box
try:
    RECORTES=json.load(open('recortes_areas.json',encoding='utf-8'))['recortes']
except (IOError,OSError,ValueError):
    RECORTES=[]
def aplica_recortes(nome,anel):
    """Devolve o anel já sem as partes que a Secretaria excluiu da unidade."""
    p=Polygon([(x,y) for x,y in anel])
    for r in RECORTES:
        if r['unidade']!=nome: continue
        if 'remover_oeste_de' in r: fora=_box(-180,-90,r['remover_oeste_de'],90)
        elif 'remover_leste_de' in r: fora=_box(r['remover_leste_de'],-90,180,90)
        elif 'remover_norte_de' in r: fora=_box(-180,r['remover_norte_de'],180,90)
        elif 'remover_sul_de' in r: fora=_box(-180,-90,180,r['remover_sul_de'])
        else: continue
        antes=p.area
        p=p.difference(fora)
        if p.geom_type=='MultiPolygon':
            p=max(p.geoms,key=lambda g:g.area)
        print('  recorte pedido pela Secretaria: %-24s -%.0f%% (%s)'
              % (nome,(1-p.area/antes)*100,r.get('motivo','')[:60]))
    if p.is_empty: return None
    return [[round(x,5),round(y,5)] for x,y in p.exterior.coords]

areas=[]
for a in d['areas']:
    anel,perdido=recorta(a['poly'])
    if anel is None:
        print('  área fora do município, descartada:',a['unidade']); continue
    if perdido>0.01:
        print('  recortada no limite municipal: %-28s -%.1f%%' % (a['unidade'],perdido*100))
    nome_unidade=' '.join(a['unidade'].split())
    anel=aplica_recortes(nome_unidade,anel)
    if anel is None:
        print('  área vazia depois do recorte, descartada:',nome_unidade); continue
    areas.append({'n':nome_unidade,'t':a['tipo'],'ll':[round(a['ll'][0],5),round(a['ll'][1],5)],
                  'info':a['info'],'ruas':a['ruas'],'poly':anel})
def entrada(k,label,areas,prov=0):
    g=geon.get(k)
    return [k,label,areas,
            round(g['lat'],5) if g else None, round(g['lon'],5) if g else None,
            prov, tracado(k)]
idx=[]
for k,v in d['indice'].items():
    idx.append(entrada(k,v['label'],v['areas']))
# --- 292 vias ausentes entram no indice como sugestao (prov=1 dentro do poligono, 2 = fora)
nomes={a['n']:i for i,a in enumerate(areas)}
def acha(base):
    base=base.strip()
    if base in nomes: return nomes[base]
    b=set(norm(base).split()); best=(0,None)
    for n,i in nomes.items():
        t=set(norm(n).split()); sc=len(b&t)/max(1,len(b|t))
        if sc>best[0]: best=(sc,i)
    return best[1] if best[0]>0.2 else None
prov=0
existentes={e[0] for e in idx}
for f in d['faltantes_det']:
    if not f['via_publica']: continue
    k=norm(f['rua'])
    if not k or k in existentes: continue
    fora='mais pr' in (f['sugestao'] or '')
    ai=acha((f['sugestao'] or '').split(' (')[0])
    if ai is None: continue
    idx.append(entrada(k,f['rua'],[ai],2 if fora else 1))
    existentes.add(k); prov+=1
print('sugeridas adicionadas ao indice:',prov)
# contatos da lista da Secretaria substituem o texto livre do KML
try:
    oficiais=json.load(open('contatos_oficiais.json',encoding='utf-8'))
except (IOError,OSError,ValueError):
    oficiais={}
import re as _re
def contato(nome,info):
    o=oficiais.get(nome)
    linhas=[]
    if o:
        linhas.append('Telefone: '+o['telefone'])
        linhas.append('Endereço: '+o['endereco'])
    m=_re.search(r'[\w.\-+]+@[\w.\-]+\.\w+',info or '')
    if m: linhas.append('E-mail: '+m.group(0))
    return chr(10).join(linhas) if linhas else info
def nome_exibido(nome):
    o=oficiais.get(nome) or {}
    return o.get('renomear') or nome
un=[{'n':nome_exibido(' '.join(u['nome'].split())),'c':u['cat'],
     'll':[round(u['ll'][0],5),round(u['ll'][1],5)],
     'info':contato(' '.join(u['nome'].split()),u['info'])} for u in d['unidades']]
print('unidades com contato oficial:',sum(1 for u in un if u['n'] in oficiais),'de',len(un))
falt=[]
for f in d['faltantes_det']:
    if not f['via_publica']: continue
    falt.append({'r':f['rua'],'ll':[f['lat'],f['lon']] if f['lat'] else None,'s':f['sugestao']})
# trechos de quadra do CNEFE, por chave normalizada de logradouro
tren={}
for nome,lista in tre.items():
    k=norm(nome)
    if not k: continue
    tren.setdefault(k,[]).extend(lista)
for v in tren.values(): v.sort(key=lambda t:t[0])
casados=sum(1 for e in idx if e[0] in tren)
# --- a malha desenhada é recortada no limite: some o que passa da divisa -----
from shapely.geometry import LineString
linhas_orig=lin['linhas']
linhas_novas=[]
mapa_ids={}
for i,l in enumerate(linhas_orig):
    if len(l)<2:
        continue
    corte=LineString([(x,y) for x,y in l]).intersection(LIMITE)
    if corte.is_empty:
        continue
    partes=list(corte.geoms) if corte.geom_type.startswith('Multi') or corte.geom_type=='GeometryCollection' else [corte]
    novos=[]
    for g in partes:
        if g.geom_type!='LineString' or g.length==0:
            continue
        novos.append(len(linhas_novas))
        linhas_novas.append([[round(x,5),round(y,5)] for x,y in g.coords])
    if novos:
        mapa_ids[i]=novos
print('polilinhas: %d antes, %d depois do recorte (%d descartadas por ficarem fora)'
      % (len(linhas_orig),len(linhas_novas),len(linhas_orig)-len(mapa_ids)))

for e in idx:
    e[6]=[n for i in e[6] for n in mapa_ids.get(i,[])]

# rua só sai do índice quando nada dela sobra dentro do município
def dentro_do_municipio(e):
    if e[6]: return True
    if e[3] is None: return True                      # sem traçado e sem ponto: não dá para testar
    return LIMITE.covers(Point(e[4],e[3]))
antes=len(idx)
fora=[e[1] for e in idx if not dentro_do_municipio(e)]
idx=[e for e in idx if dentro_do_municipio(e)]
print('ruas fora do município removidas:',antes-len(idx), ('— ex.: '+', '.join(fora[:6])) if fora else '')

# ruas que sobraram fora da área recortada deixam de pertencer àquela unidade
if RECORTES:
    from shapely.geometry import LineString as _LS
    nomes_recortados={r['unidade'] for r in RECORTES}
    poligonos={a['n']:Polygon([(x,y) for x,y in a['poly']]) for a in areas if a['n'] in nomes_recortados}
    indice_area={a['n']:i for i,a in enumerate(areas)}
    def rua_na_area(e,poly):
        for i in e[6]:
            l=linhas_novas[i] if 'linhas_novas' in dir() else lin['linhas'][i]
            if len(l)>1 and poly.intersects(_LS([(x,y) for x,y in l])): return True
        if e[6]: return False
        if e[3] is None: return True
        return poly.covers(Point(e[4],e[3]))
    podadas=0; orfas=[]
    for e in idx:
        novas=[]
        for ai in e[2]:
            nome=areas[ai]['n'] if ai<len(areas) else None
            if nome in poligonos and not rua_na_area(e,poligonos[nome]):
                podadas+=1; continue
            novas.append(ai)
        if not novas: orfas.append(e[1])
        e[2]=novas
    antes_idx=len(idx)
    idx=[e for e in idx if e[2]]
    print('ruas retiradas da abrangência por recorte:',podadas,
          '| ruas que ficaram sem unidade:',len(orfas),
          ('— ex.: '+', '.join(orfas[:8])) if orfas else '')
    for a in areas:
        if a['n'] not in poligonos: continue
        poly=poligonos[a['n']]
        chaves={e[0] for e in idx if indice_area[a['n']] in e[2]}
        a['ruas']=[r for r in a['ruas'] if norm(r) in chaves]

print('logradouros CNEFE:',len(tren),'| ruas do índice com trechos numerados:',casados,'de',len(idx))
out={'areas':areas,'idx':idx,'unidades':un,'faltantes':falt,'trechos':tren,
     'bound':json.load(open('boundary.json')),'linhas':linhas_novas}
open('final.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print('traçado casado por iniciais:',extra[0],'| por nome mais longo:',extra[1])
print('bytes',len(json.dumps(out)),'| areas',len(areas),'| ruas',len(idx),
      '| com traçado',sum(1 for e in idx if e[6]),'| unidades',len(un),'| faltantes',len(falt),
      '| polilinhas',len(out['linhas']))
