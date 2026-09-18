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
areas=[]
for a in d['areas']:
    areas.append({'n':' '.join(a['unidade'].split()),'t':a['tipo'],'ll':[round(a['ll'][0],5),round(a['ll'][1],5)],
                  'info':a['info'],'ruas':a['ruas'],
                  'poly':[[round(p[0],5),round(p[1],5)] for p in a['poly']]})
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
un=[{'n':' '.join(u['nome'].split()),'c':u['cat'],'ll':[round(u['ll'][0],5),round(u['ll'][1],5)],'info':u['info']} for u in d['unidades']]
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
print('logradouros CNEFE:',len(tren),'| ruas do índice com trechos numerados:',casados,'de',len(idx))
out={'areas':areas,'idx':idx,'unidades':un,'faltantes':falt,'trechos':tren,
     'bound':json.load(open('boundary.json')),'linhas':lin['linhas']}
open('final.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print('traçado casado por iniciais:',extra[0],'| por nome mais longo:',extra[1])
print('bytes',len(json.dumps(out)),'| areas',len(areas),'| ruas',len(idx),
      '| com traçado',sum(1 for e in idx if e[6]),'| unidades',len(un),'| faltantes',len(falt),
      '| polilinhas',len(out['linhas']))
