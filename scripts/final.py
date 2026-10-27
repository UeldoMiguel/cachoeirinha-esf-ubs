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

# inclusões de ruas na abrangência (dados/ruas_adicionadas.json)
try:
    ADICOES=json.load(open('ruas_adicionadas.json',encoding='utf-8'))['adicoes']
except (IOError,OSError,ValueError):
    ADICOES=[]

# unidades desativadas: a área e as ruas passam para quem absorveu
try:
    INATIVAS={i['unidade']:i for i in json.load(open('unidades_inativas.json',encoding='utf-8'))['inativas']}
except (IOError,OSError,ValueError):
    INATIVAS={}

# recortes manuais pedidos pela Secretaria (dados/recortes_areas.json)
from shapely.geometry import box as _box
try:
    RECORTES=json.load(open('recortes_areas.json',encoding='utf-8'))['recortes']
except (IOError,OSError,ValueError):
    RECORTES=[]
RECORTADO={}                       # unidade -> pedaço que saiu dela, para quem herdar
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
        saiu=p.intersection(fora)
        if not saiu.is_empty and r.get('transferir_orfas_para'):
            RECORTADO.setdefault(r['transferir_orfas_para'],[]).append(saiu)
        p=p.difference(fora)
        if p.geom_type=='MultiPolygon':
            p=max(p.geoms,key=lambda g:g.area)
        print('  recorte pedido pela Secretaria: %-24s -%.0f%% (%s)'
              % (nome,(1-p.area/antes)*100,r.get('motivo','')[:60]))
    if p.is_empty: return None
    return [[round(x,5),round(y,5)] for x,y in p.exterior.coords]

def limpa_finos(anel,metros=15):
    """Some com as tiras finas que sobram de um corte: erode, dilata de volta
    e simplifica. O miolo da área não se mexe."""
    p=Polygon([(x,y) for x,y in anel])
    e=metros/111320.0
    q=p.buffer(-e).buffer(e*1.05)
    if q.is_empty: return anel
    if q.geom_type=='MultiPolygon': q=max(q.geoms,key=lambda g:g.area)
    q=q.simplify(4/111320.0)
    return [[round(x,5),round(y,5)] for x,y in q.exterior.coords]

areas=[]
for _i,a in enumerate(d['areas']):
    anel,perdido=recorta(a['poly'])
    if anel is None:
        print('  área fora do município, descartada:',a['unidade']); continue
    if perdido>0.01:
        print('  recortada no limite municipal: %-28s -%.1f%%' % (a['unidade'],perdido*100))
    nome_unidade=' '.join(a['unidade'].split())
    anel=aplica_recortes(nome_unidade,anel)
    if anel is None:
        print('  área vazia depois do recorte, descartada:',nome_unidade); continue
    if perdido > 0.001 or nome_unidade in {r['unidade'] for r in RECORTES}:
        limpo=limpa_finos(anel)
        if len(limpo)!=len(anel):
            print('  tiras finas removidas da borda: %-24s %d -> %d vértices'
                  % (nome_unidade,len(anel),len(limpo)))
        anel=limpo
    areas.append({'n':nome_unidade,'t':a['tipo'],'ll':[round(a['ll'][0],5),round(a['ll'][1],5)],
                  'info':a['info'],'ruas':a['ruas'],'poly':anel,'_orig':_i})
mortas=[]
if INATIVAS:
    from shapely.ops import unary_union as _uniao
    por_nome_area={a['n']:a for a in areas}
    for nome,info in INATIVAS.items():
        morta=por_nome_area.get(nome)
        viva=por_nome_area.get(info['area_absorvida_por'])
        if not morta:
            continue
        if viva:
            juntas=_uniao([Polygon([(x,y) for x,y in morta['poly']]).buffer(0),
                           Polygon([(x,y) for x,y in viva['poly']]).buffer(0)])
            e=25/111320.0
            juntas=juntas.buffer(e).buffer(-e)          # fecha a folga entre os dois desenhos
            if juntas.geom_type=='MultiPolygon':
                juntas=max(juntas.geoms,key=lambda g:g.area)
            viva['poly']=[[round(x,5),round(y,5)] for x,y in juntas.simplify(3/111320.0).exterior.coords]
            viva['ruas']=sorted(set(viva['ruas'])|set(morta['ruas']))
            print('unidade desativada: %s -> área e %d ruas para %s'
                  % (nome,len(morta['ruas']),info['area_absorvida_por']))
        else:
            print('unidade desativada: %s (sem sucessora indicada, área removida)' % nome)
        morta['_sucessora']=viva['_orig'] if viva else None
        areas.remove(morta)
        mortas.append(morta)
    # o ponto da unidade some do mapa
    d['unidades']=[u for u in d['unidades'] if ' '.join(u['nome'].split()) not in INATIVAS]

# de índice antigo (posição em d['areas']) para índice novo; área desativada
# cai na sucessora, área descartada some
# o pedaço que saiu de uma unidade vira um polígono à parte da unidade que
# herdou as ruas: os dois territórios ficam no mesmo desenho, sem se tocarem
if RECORTADO:
    from shapely.ops import unary_union as _u3
    por_nome_area={a['n']:a for a in areas}
    for nome,pedacos in RECORTADO.items():
        alvo=por_nome_area.get(nome)
        if not alvo:
            print('pedaço recortado sem unidade para herdar:',nome); continue
        g=_u3([q.buffer(0) for q in pedacos])
        e=15/111320.0
        g=g.buffer(-e).buffer(e*1.05)                 # tira as tiras finas da borda do corte
        partes=list(g.geoms) if g.geom_type=='MultiPolygon' else ([g] if not g.is_empty else [])
        partes=[q.simplify(4/111320.0) for q in partes if q.area>2e-7]   # ~2.500 m2
        alvo['poly_extra']=[[[round(x,5),round(y,5)] for x,y in q.exterior.coords] for q in partes]
        print('polígono separado anexado a %s: %d parte(s), %.2f km2'
              % (nome,len(partes),sum(q.area for q in partes)*111.32**2))

REMAP={a['_orig']:i for i,a in enumerate(areas)}
for m in mortas:
    if m.get('_sucessora') is not None and m['_sucessora'] in REMAP:
        REMAP[m['_orig']]=REMAP[m['_sucessora']]

if ADICOES:
    from shapely.geometry import LineString as _LS, MultiLineString as _MLS
    from shapely.ops import unary_union as _u2
    por_nome_area={a['n']:a for a in areas}
    for add in ADICOES:
        alvo=por_nome_area.get(add['unidade'])
        if not alvo:
            print('inclusão ignorada, unidade não encontrada:',add['unidade']); continue
        alvo['ruas']=sorted(set(alvo['ruas'])|set(add['ruas']))
        if add.get('estender_area'):
            segs=[]
            for nome in add['ruas']:
                for i in lin['porNome'].get(nome,[]):
                    l=lin['linhas'][i]
                    if len(l)>1: segs.append(_LS([(x,y) for x,y in l]))
            if segs:
                mancha=_MLS(segs).convex_hull.buffer(25/111320.0)
                j=_u2([Polygon([(x,y) for x,y in alvo['poly']]).buffer(0),mancha])
                if j.geom_type=='MultiPolygon': j=max(j.geoms,key=lambda g:g.area)
                antes=Polygon([(x,y) for x,y in alvo['poly']]).area
                alvo['poly']=[[round(x,5),round(y,5)] for x,y in j.simplify(3/111320.0).exterior.coords]
                print('área estendida: %-22s +%.1f%% para cobrir %d vias incluídas'
                      % (add['unidade'],(j.area/antes-1)*100,len(add['ruas'])))
        print('ruas incluídas na abrangência de %s: %d' % (add['unidade'],len(add['ruas'])))

# transferências de território pedidas pela Secretaria (dados/areas_transferidas.json)
try:
    TRANSF=json.load(open('areas_transferidas.json',encoding='utf-8'))['transferencias']
except (IOError,OSError,ValueError,KeyError):
    TRANSF=[]
REGIOES={}                        # unidade de destino -> regiões que ela recebeu
if TRANSF:
    from shapely.geometry import LineString as _LS3
    from shapely.ops import unary_union as _u4, linemerge as _lm, substring as _sub

    def _via(nome):
        """Traçado inteiro de uma via do OpenStreetMap, emendado ponta a ponta."""
        partes=[_LS3([(x,y) for x,y in lin['linhas'][i]])
                for i in lin['porNome'].get(nome,[]) if len(lin['linhas'][i])>1]
        if not partes: return None
        g=_u4(partes)
        g=_lm(g) if g.geom_type=='MultiLineString' else g
        return max(g.geoms,key=lambda q:q.length) if g.geom_type=='MultiLineString' else g

    def regiao_entre_vias(eixo,lados):
        """Região cercada por três vias.

        O 'eixo' precisa ir de uma via de 'lados' até a outra. O contorno é o
        eixo inteiro, mais o pedaço de cada lateral entre o eixo e o ponto em
        que as duas laterais se encontram. Nada é desenhado à mão: o traçado
        todo vem do OpenStreetMap.
        """
        e=_via(eixo); a=_via(lados[0]); b=_via(lados[1])
        if e is None or a is None or b is None: return None
        p0,p1=Point(e.coords[0]),Point(e.coords[-1])
        if a.distance(p0)>a.distance(p1):          # p0 é a ponta que encosta em 'a'
            p0,p1=p1,p0
        eixo_pts=list(e.coords)
        if Point(eixo_pts[0]).distance(p0)>Point(eixo_pts[-1]).distance(p0):
            eixo_pts=list(reversed(eixo_pts))
        # de 'a': do encontro com o eixo até a ponta que chega em 'b'
        fim_a=a.length if Point(a.coords[-1]).distance(b)<Point(a.coords[0]).distance(b) else 0.0
        ta=_sub(a,a.project(p0),fim_a)
        if ta.is_empty: return None
        canto=Point(list(ta.coords)[-1])
        tb=_sub(b,b.project(p1),b.project(canto))   # de 'b': do eixo até esse canto
        if tb.is_empty: return None
        anel=eixo_pts+list(tb.coords)+list(reversed(list(ta.coords)))
        reg=Polygon(anel).buffer(0)
        if reg.is_empty: return None
        if reg.geom_type=='MultiPolygon': reg=max(reg.geoms,key=lambda g:g.area)
        return reg.intersection(LIMITE)

    por_nome_area={a['n']:a for a in areas}

    def partes(a2):
        return [Polygon(a2['poly']).buffer(0)]+[Polygon(r).buffer(0) for r in a2.get('poly_extra') or []]

    def so_poligonos(g):
        """Interseção pode devolver linhas e pontos junto: fica só a área."""
        if g.is_empty: return g
        if g.geom_type in ('Polygon','MultiPolygon'): return g
        return unary_union([q for q in getattr(g,'geoms',[]) if q.geom_type in ('Polygon','MultiPolygon')])

    def guarda(a2,qs):
        qs=[q for q in qs if not q.is_empty and q.geom_type=='Polygon']
        qs.sort(key=lambda q:-q.area)
        a2['poly']=[[round(x,5),round(y,5)] for x,y in qs[0].exterior.coords]
        extras=[[[round(x,5),round(y,5)] for x,y in q.exterior.coords] for q in qs[1:]]
        if extras: a2['poly_extra']=extras
        elif 'poly_extra' in a2: a2.pop('poly_extra')

    for t in TRANSF:
        if (t.get('pedaco_em') or t.get('caixa')
                or any(t.get('ao_'+l+'_da_via') for l in ('norte','sul','leste','oeste'))):
            continue                      # tratados no fim, sobre a área já pronta
        reg=regiao_entre_vias(t['eixo'],t['lados'])
        if reg is None or reg.is_empty:
            print('transferência ignorada, região não pôde ser fechada:',t.get('para')); continue
        alvo=por_nome_area.get(t['para'])
        if not alvo:
            print('transferência ignorada, unidade não encontrada:',t['para']); continue
        # a transferência só pega o que está vago ou pertence a quem foi listado:
        # o território de qualquer outra unidade sai da região e fica como está
        poupadas=set(t.get('retirar_de',[]))|{t['para']}
        alheio=[Polygon(a2['poly']).buffer(0) for a2 in areas if a2['n'] not in poupadas]
        alheio+= [Polygon(r).buffer(0) for a2 in areas if a2['n'] not in poupadas
                  for r in a2.get('poly_extra') or []]
        if alheio:
            antes_reg=reg.area
            reg=reg.difference(unary_union(alheio))
            if reg.is_empty:
                print('transferência vazia depois de respeitar as vizinhas:',t['para']); continue
            if reg.geom_type=='MultiPolygon': reg=max(reg.geoms,key=lambda g:g.area)
            if reg.area<antes_reg:
                print('região reduzida a %.0f%%: o resto já é de outra unidade' % (100*reg.area/antes_reg))
        for nome in t.get('retirar_de',[]):
            velha=por_nome_area.get(nome)
            if not velha: continue
            p=Polygon(velha['poly']).buffer(0)
            sobra=p.difference(reg)
            if sobra.is_empty: continue
            if sobra.geom_type=='MultiPolygon': sobra=max(sobra.geoms,key=lambda g:g.area)
            e2=15/111320.0
            sobra=sobra.buffer(-e2).buffer(e2*1.05).simplify(4/111320.0)
            if sobra.is_empty: continue
            if sobra.geom_type=='MultiPolygon': sobra=max(sobra.geoms,key=lambda g:g.area)
            print('região transferida: %-22s -%.0f%% da área' % (nome,(1-sobra.area/p.area)*100))
            velha['poly']=[[round(x,5),round(y,5)] for x,y in sobra.exterior.coords]
        principal=Polygon(alvo['poly']).buffer(0)
        if principal.intersects(reg):
            # encosta no território da unidade: vira um desenho só, sem divisa interna
            j=_u2([principal,reg]).buffer(0)
            if j.geom_type=='MultiPolygon': j=max(j.geoms,key=lambda g:g.area)
            alvo['poly']=[[round(x,5),round(y,5)] for x,y in j.simplify(3/111320.0).exterior.coords]
            print('região de %.2f km2 unida ao território da %s (+%.0f%%)'
                  % (reg.area*111.32**2,t['para'],(j.area/principal.area-1)*100))
        else:
            # território distante: entra como parte separada, sem ponte até a área principal
            alvo.setdefault('poly_extra',[]).append(
                [[round(x,5),round(y,5)] for x,y in reg.simplify(3/111320.0).exterior.coords])
            print('região de %.2f km2 anexada à %s como polígono separado'
                  % (reg.area*111.32**2,t['para']))
        REGIOES.setdefault(t['para'],[]).append(reg)


# vazios de cobertura: todo pedaço do município que não está em área nenhuma
# passa para a UBS mais próxima (dados/vazios.json)
try:
    VAZIOS=json.load(open('vazios.json',encoding='utf-8'))
except (IOError,OSError,ValueError):
    VAZIOS={}
if VAZIOS.get('distribuir') and areas:
    from shapely.geometry import MultiPoint as _MP
    from shapely.ops import voronoi_diagram as _vor
    minimo=VAZIOS.get('area_minima_m2',2000)/(111320.0**2)
    def _todas(a):
        return [Polygon(a['poly']).buffer(0)]+[Polygon(r).buffer(0) for r in a.get('poly_extra') or []]
    cobertura=unary_union([q for a in areas for q in _todas(a)])
    vazio=LIMITE.difference(cobertura)
    tipo=VAZIOS.get('entre','UBS')
    pontos=[(' '.join(u['nome'].split()),Point(u['ll'][1],u['ll'][0]))
            for u in d['unidades'] if u['cat']==tipo]
    por_nome_area={a['n']:a for a in areas}
    pontos=[(n,p) for n,p in pontos if n in por_nome_area]
    # exceções: o vazio de um polígono nomeado vai para a unidade indicada,
    # antes da divisão automática pela unidade mais próxima
    try:
        POLIS=json.load(open('osm_poligonos.json',encoding='utf-8'))['poligonos']
    except (IOError,OSError,ValueError,KeyError):
        POLIS={}
    for exc in VAZIOS.get('excecoes',[]):
        alvo=por_nome_area.get(exc['para'])
        rotulo=exc.get('poligono') or 'caixa'
        if exc.get('caixa'):
            sul,oeste,norte,leste=exc['caixa']
            molde=_box(oeste,sul,leste,norte)
        else:
            reg=POLIS.get(exc.get('poligono'))
            molde=Polygon(reg['anel']).buffer(0) if reg else None
        if molde is None or not alvo:
            print('exceção ignorada:',rotulo,'->',exc.get('para')); continue
        parte=vazio.intersection(molde)
        if parte.is_empty:
            print('exceção sem vazio para distribuir:',rotulo); continue
        j=unary_union(_todas(alvo)+[parte])
        qs=[q for q in (j.geoms if j.geom_type=='MultiPolygon' else [j]) if q.area>minimo]
        qs.sort(key=lambda q:-q.area)
        alvo['poly']=[[round(x,5),round(y,5)] for x,y in qs[0].simplify(3/111320.0).exterior.coords]
        extras=[[[round(x,5),round(y,5)] for x,y in q.simplify(3/111320.0).exterior.coords] for q in qs[1:]]
        if extras: alvo['poly_extra']=extras
        REGIOES.setdefault(exc['para'],[]).append(parte)
        vazio=vazio.difference(parte)
        print('exceção: %s (%.2f km2) -> %s' % (rotulo,parte.area*111.32**2,exc['para']))

    if not vazio.is_empty and len(pontos)>1:
        # células de Voronoi: cada ponto do vazio fica com a unidade mais próxima
        celulas=_vor(_MP([p for _,p in pontos]),envelope=LIMITE.buffer(0.02))
        de_quem={}
        for g in celulas.geoms:
            for n,p in pontos:
                if g.contains(p): de_quem[n]=g; break
        e3=10/111320.0
        total=0.0
        for nome,celula in sorted(de_quem.items()):
            parte=vazio.intersection(celula)
            if parte.is_empty: continue
            parte=parte.buffer(e3).buffer(-e3)              # tira os fiapos da divisa
            if parte.is_empty: continue
            alvo=por_nome_area[nome]
            j=unary_union(_todas(alvo)+[parte])
            qs=list(j.geoms) if j.geom_type=='MultiPolygon' else [j]
            qs=[q for q in qs if q.area>minimo]
            if not qs: continue
            qs.sort(key=lambda q:-q.area)
            qs=[q.simplify(3/111320.0) for q in qs]
            alvo['poly']=[[round(x,5),round(y,5)] for x,y in qs[0].exterior.coords]
            extras=[[[round(x,5),round(y,5)] for x,y in q.exterior.coords] for q in qs[1:]]
            if extras: alvo['poly_extra']=extras
            elif 'poly_extra' in alvo: del alvo['poly_extra']
            REGIOES.setdefault(nome,[]).append(parte)
            total+=parte.area*111.32**2
            print('vazio distribuído: %-26s +%5.2f km2  (%d parte%s)'
                  % (nome[:26],parte.area*111.32**2,len(qs),'' if len(qs)==1 else 's'))
        print('área sem referência distribuída: %.2f km2' % total)

# partes da mesma unidade que se encostam viram um desenho só: duas metades
# coladas pela ponta ficariam com uma divisa à toa no meio do território
for a in areas:
    if not a.get('poly_extra'): continue
    pecas=[Polygon(a['poly']).buffer(0)]+[Polygon(r).buffer(0) for r in a['poly_extra']]
    e4=5/111320.0
    j=unary_union(pecas).buffer(e4).buffer(-e4)
    qs=list(j.geoms) if j.geom_type=='MultiPolygon' else [j]
    if len(qs)>=len(pecas): continue
    qs=[q.simplify(3/111320.0) for q in sorted(qs,key=lambda q:-q.area)]
    a['poly']=[[round(x,5),round(y,5)] for x,y in qs[0].exterior.coords]
    if qs[1:]: a['poly_extra']=[[[round(x,5),round(y,5)] for x,y in q.exterior.coords] for q in qs[1:]]
    else: a.pop('poly_extra')
    print('partes encostadas unidas: %-26s %d -> %d' % (a['n'][:26],len(pecas),len(qs)))

# pedaços avulsos que mudam de unidade (entradas com 'pedaco_em' em
# dados/areas_transferidas.json): aplicados sobre a área já pronta
if TRANSF:
    por_nome_area={a['n']:a for a in areas}

    def partes(a2):
        return [Polygon(a2['poly']).buffer(0)]+[Polygon(r).buffer(0) for r in a2.get('poly_extra') or []]

    def so_poligonos(g):
        """Interseção pode devolver linhas e pontos junto: fica só a área."""
        if g.is_empty: return g
        if g.geom_type in ('Polygon','MultiPolygon'): return g
        return unary_union([q for q in getattr(g,'geoms',[]) if q.geom_type in ('Polygon','MultiPolygon')])

    def guarda(a2,qs):
        qs=[q for q in qs if not q.is_empty and q.geom_type=='Polygon']
        qs.sort(key=lambda q:-q.area)
        a2['poly']=[[round(x,5),round(y,5)] for x,y in qs[0].exterior.coords]
        extras=[[[round(x,5),round(y,5)] for x,y in q.exterior.coords] for q in qs[1:]]
        if extras: a2['poly_extra']=extras
        elif 'poly_extra' in a2: a2.pop('poly_extra')

    def lado_da_via(nome,lado,molde_bbox):
        """Polígono com tudo que fica de um lado da via (norte, sul, leste ou
        oeste): o traçado do OSM, fechado contra a borda daquele lado."""
        v=_via(nome)
        if v is None: return None
        minx,miny,maxx,maxy=molde_bbox
        minx-=0.02; maxx+=0.02; miny-=0.02; maxy+=0.02
        c=list(v.coords)
        if lado in ('norte','sul'):
            if c[0][0]>c[-1][0]: c=list(reversed(c))      # de oeste para leste
            borda=maxy if lado=='norte' else miny
            anel=[(minx,c[0][1])]+c+[(maxx,c[-1][1]),(maxx,borda),(minx,borda)]
        else:
            if c[0][1]>c[-1][1]: c=list(reversed(c))      # de sul para norte
            borda=maxx if lado=='leste' else minx
            anel=[(c[0][0],miny)]+c+[(c[-1][0],maxy),(borda,maxy),(borda,miny)]
        p=Polygon(anel).buffer(0)
        return p if not p.is_empty else None

    for t in TRANSF:
        lado=([l for l in ('norte','sul','leste','oeste') if t.get('ao_'+l+'_da_via')] or [None])[0]
        if lado or t.get('caixa'):
            origem=por_nome_area.get(t.get('de')); alvo=por_nome_area.get(t['para'])
            if not origem or not alvo:
                print('transferência ignorada:',t.get('de'),'->',t.get('para')); continue
            seu=unary_union(partes(origem))
            # os critérios se somam: caixa e lado de via valem ao mesmo tempo
            molde=None; rotulo=[]
            if t.get('caixa'):
                sul,oeste,norte,leste=t['caixa']
                molde=_box(oeste,sul,leste,norte); rotulo.append('caixa')
            if lado:
                m2=lado_da_via(t['ao_'+lado+'_da_via'],lado,seu.bounds)
                if m2 is None:
                    print('via não encontrada:',t['ao_'+lado+'_da_via']); continue
                molde=m2 if molde is None else molde.intersection(m2)
                rotulo.append('ao %s da %s' % (lado,t['ao_'+lado+'_da_via']))
            vai=so_poligonos(seu.intersection(molde)); fica=so_poligonos(seu.difference(molde))
            if vai.is_empty:
                print('nada a mover: %s não tem área em %s' % (t['de'],' + '.join(rotulo))); continue
            qs=[q for q in (fica.geoms if fica.geom_type=='MultiPolygon' else [fica])
                if q.area>2000/(111320.0**2)]
            if not qs:
                print('o corte pega a área inteira de %s, ignorado' % t['de']); continue
            guarda(origem,qs)
            j=unary_union(partes(alvo)+[vai])
            guarda(alvo,list(j.geoms) if j.geom_type=='MultiPolygon' else [j])
            REGIOES.setdefault(t['para'],[]).append(vai)
            print('%s: %.3f km2  %s -> %s' % (' + '.join(rotulo),vai.area*111.32**2,t['de'],t['para']))
            continue
        if False:
            # move o que a unidade de origem tem dentro da caixa
            origem=por_nome_area.get(t.get('de')); alvo=por_nome_area.get(t['para'])
            if not origem or not alvo:
                print('transferência por caixa ignorada:',t.get('de'),'->',t.get('para')); continue
            sul,oeste,norte,leste=t['caixa']
            molde=_box(oeste,sul,leste,norte)
            seu=unary_union(partes(origem))
            vai=seu.intersection(molde)
            if vai.is_empty:
                print('caixa sem área de %s dentro' % t['de']); continue
            fica=seu.difference(molde)
            if fica.is_empty:
                print('a caixa pega a área inteira de %s, transferência ignorada' % t['de']); continue
            # o corte é reto: basta descartar lasca menor que 2.000 m2, sem
            # erodir a borda — erodir abriria uma fresta entre as duas áreas
            qs=list(fica.geoms) if fica.geom_type=='MultiPolygon' else [fica]
            qs=[q for q in qs if q.area>2000/(111320.0**2)]
            if not qs:
                print('a caixa pega a área inteira de %s, transferência ignorada' % t['de']); continue
            guarda(origem,qs)
            j=unary_union(partes(alvo)+[vai])
            guarda(alvo,list(j.geoms) if j.geom_type=='MultiPolygon' else [j])
            REGIOES.setdefault(t['para'],[]).append(vai)
            print('caixa de %.3f km2: %s -> %s' % (vai.area*111.32**2,t['de'],t['para']))
            continue
        if not t.get('pedaco_em'): continue
        origem=por_nome_area.get(t.get('de')); alvo=por_nome_area.get(t['para'])
        if not origem or not alvo:
            print('transferência de pedaço ignorada:',t.get('de'),'->',t.get('para')); continue
        lat,lon=t['pedaco_em']; ponto=Point(lon,lat)
        qs=partes(origem)
        vai=[q for q in qs if q.contains(ponto)]
        fica=[q for q in qs if not q.contains(ponto)]
        if not vai:
            print('nenhum pedaço de %s contém %.5f,%.5f' % (t['de'],lat,lon)); continue
        if not fica:
            print('o pedaço é a área inteira de %s, transferência ignorada' % t['de']); continue
        guarda(origem,fica)
        j=unary_union(partes(alvo)+vai)
        guarda(alvo,list(j.geoms) if j.geom_type=='MultiPolygon' else [j])
        REGIOES.setdefault(t['para'],[]).append(unary_union(vai))
        print('pedaço de %.3f km2: %s -> %s' % (sum(q.area for q in vai)*111.32**2,t['de'],t['para']))

# nenhuma área pode cobrir outra: onde duas se sobrepõem, o território fica
# com a ESF (equipe de Saúde da Família vinculada) e sai da UBS. O que sobra
# cercado vira buraco no desenho da UBS, em vez de engolir a vizinha.
def _geom(a2):
    pecas=[Polygon(a2['poly']).buffer(0)]+[Polygon(r).buffer(0) for r in a2.get('poly_extra') or []]
    g=unary_union(pecas)
    for r in a2.get('buracos') or []:
        g=g.difference(Polygon(r).buffer(0))
    return g

def _grava(a2,g):
    if g.is_empty: return False
    qs=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
    qs=[q for q in qs if q.area>2000/(111320.0**2)]
    if not qs: return False
    qs.sort(key=lambda q:-q.area)
    a2['poly']=[[round(x,5),round(y,5)] for x,y in qs[0].exterior.coords]
    extras=[[[round(x,5),round(y,5)] for x,y in q.exterior.coords] for q in qs[1:]]
    if extras: a2['poly_extra']=extras
    elif 'poly_extra' in a2: a2.pop('poly_extra')
    furos=[[[round(x,5),round(y,5)] for x,y in anel.coords] for q in qs for anel in q.interiors]
    if furos: a2['buracos']=furos
    elif 'buracos' in a2: a2.pop('buracos')
    return True

esf=[a for a in areas if a['t']=='ESF']
for a in areas:
    if a['t']=='ESF': continue
    g=_geom(a)
    for b in esf:
        gb=_geom(b)
        if g.intersects(gb): g=g.difference(gb)
    if not _grava(a,g):
        print('aviso: área da %s ficou vazia depois de respeitar as ESF' % a['n'])
    elif a.get('buracos'):
        print('buraco no desenho: %-26s %d área(s) de ESF cercada(s)' % (a['n'][:26],len(a['buracos'])))

def entrada(k,label,indices,prov=0,traduzir=True):
    g=geon.get(k)
    if traduzir:
        vistos=[]
        for i in indices:
            novo=REMAP.get(i)
            if novo is not None and novo not in vistos: vistos.append(novo)
        indices=vistos
    return [k,label,indices,
            round(g['lat'],5) if g else None, round(g['lon'],5) if g else None,
            prov, tracado(k)]
idx=[]
for k,v in d['indice'].items():
    e=entrada(k,v['label'],v['areas'])
    if e[2]: idx.append(e)                  # sem área nenhuma, a rua não entra
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
    idx.append(entrada(k,f['rua'],[ai],2 if fora else 1,traduzir=False))
    existentes.add(k); prov+=1
print('sugeridas adicionadas ao indice:',prov)
if ADICOES:
    pos={a['n']:i for i,a in enumerate(areas)}
    por_chave={e[0]:e for e in idx}
    incluidas=0
    for add in ADICOES:
        ai=pos.get(add['unidade'])
        if ai is None: continue
        for nome in add['ruas']:
            k=norm(nome)
            e=por_chave.get(k)
            if e is None:
                e=entrada(k,nome,[ai],0,traduzir=False)
                idx.append(e); por_chave[k]=e; incluidas+=1
            elif ai not in e[2]:
                e[2].append(ai); incluidas+=1
    print('vias incluídas no índice:',incluidas)
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
    if o and 'email' in o:
        # a lista da Secretaria manda também no e-mail; '' diz que não há
        if o['email']: linhas.append('E-mail: '+o['email'])
    else:
        m=_re.search(r'[\w.\-+]+@[\w.\-]+\.\w+',info or '')
        if m: linhas.append('E-mail: '+m.group(0))
    return chr(10).join(linhas) if linhas else info
def nome_exibido(nome):
    o=oficiais.get(nome) or {}
    return o.get('renomear') or nome
# linhas que não atendem por WhatsApp (dados/whatsapp.json): o número aparece
# igual na página, só não vira link
try:
    SEM_WA=json.load(open('whatsapp.json',encoding='utf-8'))['sem_link']
except (IOError,OSError,ValueError,KeyError):
    SEM_WA={}
def sem_wa(nome):
    v=SEM_WA.get(nome)
    return True if v=='todos' else (list(v) if v else None)
un=[{'n':nome_exibido(' '.join(u['nome'].split())),'c':u['cat'],
     'll':[round(u['ll'][0],5),round(u['ll'][1],5)],
     'nowa':sem_wa(nome_exibido(' '.join(u['nome'].split()))),
     'info':contato(' '.join(u['nome'].split()),u['info'])} for u in d['unidades']]
un=[{k:v for k,v in u.items() if v is not None} for u in un]
# serviços que só constam da lista da Secretaria, sem alfinete no mapa
# colaborativo: entram pela coordenada do próprio endereço, para não faltarem
nomes_un={u['n'] for u in un}
for nome,o in sorted(oficiais.items()):
    exibido=o.get('renomear') or nome
    if exibido in nomes_un or not o.get('ll'): continue
    nomes_un.add(exibido)
    novo={'n':exibido,'c':o.get('tipo') or 'Especialidades',
          'll':[round(o['ll'][0],5),round(o['ll'][1],5)],
          'nowa':sem_wa(exibido),'info':contato(nome,'')}
    un.append({k:v for k,v in novo.items() if v is not None})
    print('serviço acrescentado da lista oficial:',exibido)
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

# as ruas com traçado dentro de uma região transferida passam a responder
# pela unidade que a recebeu; quem também atravessa a área antiga continua nas
# duas, e aí o número da casa é que decide
if REGIOES:
    from shapely.geometry import LineString as _LS4
    indice_area={a['n']:i for i,a in enumerate(areas)}
    for destino,regioes in REGIOES.items():
        ai=indice_area.get(destino)
        if ai is None: continue
        reg=regioes[0] if len(regioes)==1 else _u2(regioes)
        ganhas=[]
        for e in idx:
            if ai in e[2] or not e[6]: continue
            for i in e[6]:
                l=linhas_novas[i]
                if len(l)>1 and reg.intersects(_LS4([(x,y) for x,y in l])):
                    e[2].append(ai); ganhas.append(e[1]); break
        if ganhas:
            areas[ai]['ruas']=sorted(set(areas[ai]['ruas'])|set(ganhas))
            print('ruas da região transferida para %s: %d — ex.: %s'
                  % (destino,len(ganhas),', '.join(sorted(ganhas)[:6])))

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
    # para quem vão as ruas que o recorte deixou sem unidade
    herdeiro={}
    for r in RECORTES:
        if r.get('transferir_orfas_para'):
            herdeiro[r['unidade']]=r['transferir_orfas_para']
    indice_por_nome={a['n']:i for i,a in enumerate(areas)}
    podadas=0; orfas=[]; transferidas={}
    for e in idx:
        novas=[]; perdeu=[]
        for ai in e[2]:
            nome=areas[ai]['n'] if ai<len(areas) else None
            if nome in poligonos and not rua_na_area(e,poligonos[nome]):
                podadas+=1; perdeu.append(nome); continue
            novas.append(ai)
        if not novas:
            for nome in perdeu:
                destino=indice_por_nome.get(herdeiro.get(nome))
                if destino is not None and destino not in novas:
                    novas.append(destino)
                    transferidas.setdefault(herdeiro[nome],[]).append(e[1])
        if not novas: orfas.append(e[1])
        e[2]=novas
    for destino,ruas in transferidas.items():
        areas[indice_por_nome[destino]]['ruas']=sorted(set(areas[indice_por_nome[destino]]['ruas'])|set(ruas))
        print('ruas do setor recortado transferidas para %s: %d' % (destino,len(ruas)))
    antes_idx=len(idx)
    idx=[e for e in idx if e[2]]
    print('ruas retiradas da abrangência por recorte:',podadas,
          '| ruas que ficaram sem unidade:',len(orfas),
          ('— ex.: '+', '.join(orfas[:8])) if orfas else '')
    for a in areas:
        if a['n'] not in poligonos or a['n'] in herdeiro.values(): continue
        poly=poligonos[a['n']]
        chaves={e[0] for e in idx if indice_area[a['n']] in e[2]}
        a['ruas']=[r for r in a['ruas'] if norm(r) in chaves]

print('logradouros CNEFE:',len(tren),'| ruas do índice com trechos numerados:',casados,'de',len(idx))
# verbetes com faixa de numeração — "Espanha (575 ao 921)" — ganham o traçado
# da própria via e passam a valer como faixa na rua-base: com o número da casa,
# a consulta responde a unidade daquele trecho, não a da via inteira
FAIXA=_re.compile(r'^(.*?)\s*\(([^)]*\d[^)]*)\)\s*$')
NUMS=_re.compile(r'(\d+)\s*(?:a|ao|at[eé]|[-–])\s*(\d+)|(\d+)')
por_chave={e[0]:e for e in idx}
amarrados=casadas=0
for e in idx:
    m=FAIXA.match(e[1])
    if not m: continue
    base=norm(m.group(1))
    if not e[6] and base in linn:
        e[6]=list(linn[base])                      # desenha no traçado da via
        amarrados+=1
    g=geon.get(base)
    if e[3] is None and g:
        e[3],e[4]=round(g['lat'],5),round(g['lon'],5)
    mae=por_chave.get(base)
    if mae is None or mae is e or not e[2]: continue
    txt=m.group(2).lower()
    par=1 if 'impar' in txt or 'ímpar' in txt else (2 if 'par' in txt else 0)
    trechos_num=[]
    for a1,b1,so in NUMS.findall(txt):
        if a1 and b1: trechos_num.append((int(a1),int(b1)))
        elif so: trechos_num.append((int(so),int(so)))
    if txt.startswith('at') and trechos_num:          # "(até 49)"
        trechos_num=[(0,trechos_num[0][1])]
    if not trechos_num: continue
    faixas=mae[7] if len(mae)>7 else []
    for lo,hi in trechos_num:
        if lo>hi: lo,hi=hi,lo
        faixas.append([lo,hi,par,e[2][0]])
    if len(mae)>7: mae[7]=faixas
    else: mae.append(faixas)
    casadas+=1
for e in idx:
    if len(e)==7: e.append(None)
print('verbetes com faixa: traçado amarrado em %d | faixas ligadas à rua-base: %d' % (amarrados,casadas))

for a in areas: a.pop('_orig',None)
out={'areas':areas,'idx':idx,'unidades':un,'faltantes':falt,'trechos':tren,
     'bound':json.load(open('boundary.json')),'linhas':linhas_novas}
open('final.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print('traçado casado por iniciais:',extra[0],'| por nome mais longo:',extra[1])
print('bytes',len(json.dumps(out)),'| areas',len(areas),'| ruas',len(idx),
      '| com traçado',sum(1 for e in idx if e[6]),'| unidades',len(un),'| faltantes',len(falt),
      '| polilinhas',len(out['linhas']))
