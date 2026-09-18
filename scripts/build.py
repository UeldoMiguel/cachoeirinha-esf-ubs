import json,re,unicodedata,math
data=json.load(open('data.json',encoding='utf-8'))
osm=json.load(open('osm_streets.json',encoding='utf-8'))

def strip_acc(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
TIPOS={'rua':'r','r':'r','avenida':'av','av':'av','travessa':'tv','trav':'tv','tv':'tv','beco':'bc','bc':'bc','estrada':'est','est':'est','praca':'pc','pça':'pc','pc':'pc','alameda':'al','al':'al','rodovia':'rod','rod':'rod','largo':'lg','via':'via','acesso':'ac','viela':'vl','passagem':'pss','linha':'lnh','servidao':'srv','esquina':'esq'}
NUM={'primeiro':'1','primeira':'1','segundo':'2','segunda':'2','terceiro':'3','terceira':'3','um':'1','uma':'1','dois':'2','duas':'2','tres':'3','quatro':'4','cinco':'5','seis':'6','sete':'7','oito':'8','nove':'9','dez':'10','onze':'11','doze':'12','treze':'13','quatorze':'14','catorze':'14','quinze':'15','dezesseis':'16','dezessete':'17','dezoito':'18','dezenove':'19','vinte':'20','trinta':'30','quarenta':'40','cinquenta':'50'}
ABREV={'sto':'santo','sta':'santa','s':'sao','sao':'sao','dr':'doutor','dra':'doutora','prof':'professor','profa':'professora','pe':'padre','cel':'coronel','gal':'general','gen':'general','cap':'capitao','ten':'tenente','sgt':'sargento','mal':'marechal','maj':'major','eng':'engenheiro','pres':'presidente','vda':'viuva','d':'dom','pq':'parque','jd':'jardim','cj':'conjunto','vl':'vila'}
def norm(s):
    s=strip_acc(str(s)).lower()
    s=re.sub(r'[^a-z0-9 ]',' ',s)
    toks=[t for t in s.split() if t]
    if toks and toks[0] in TIPOS: toks=toks[1:]
    toks=[ABREV.get(t,t) for t in toks]
    toks=[t for t in toks if t not in ('de','da','do','das','dos','e','no','na')]
    toks=[str(int(t)) if t.isdigit() else t for t in toks]
    toks=[NUM.get(t,t) for t in toks]
    # junta numerais escritos: "trinta um" -> "31" ja tratado abaixo
    out=[]
    for t in toks:
        if out and out[-1].isdigit() and t.isdigit() and int(out[-1])%10==0 and int(out[-1])>=20 and int(t)<10:
            out[-1]=str(int(out[-1])+int(t))
        else: out.append(t)
    return ' '.join(out)
def tipo(s):
    t=strip_acc(str(s)).lower().split()
    return TIPOS.get(t[0],'') if t else ''

def parse_streets(desc):
    txt=re.sub(r'<br\s*/?>','\n',desc,flags=re.I)
    txt=re.sub(r'<[^>]+>','',txt)
    out=[]
    for ln in txt.split('\n'):
        ln=' '.join(ln.split())
        if not ln: continue
        if '@' in ln or re.match(r'(?i)^(email|e-mail|tel|fone|telefone|endere)',ln): continue
        out.append(ln)
    return out

units=[]   # points
areas=[]
for folder,items in data.items():
    for it in items:
        nm=' '.join(it['name'].split())
        if 'poly' in it:
            tipo_a='ESF' if folder.startswith('Área ESF') or nm.upper().startswith('ESF') else 'UBS'
            areas.append({'nome':nm,'tipo':tipo_a,'ruas':parse_streets(it['desc']),'poly':it['poly']})
        elif 'point' in it:
            units.append({'nome':nm,'cat':folder,'ll':[it['point'][1],it['point'][0]],'info':re.sub('<[^>]+>','\n',it['desc']).strip()})

# link area -> unit point
def best(nm,cands):
    a=set(norm(nm).split())
    bs,bu=0,None
    for u in cands:
        b=set(norm(u['nome']).split())
        sc=len(a&b)/max(1,len(a|b))
        if sc>bs: bs,bu=sc,u
    return bu if bs>0.2 else None
pts=[u for u in units if u['cat'] in ('UBS','ESF')]
for a in areas:
    u=best(a['nome'],[p for p in pts if p['cat']==a['tipo']])
    a['unidade']=u['nome'] if u else a['nome']
    a['ll']=u['ll'] if u else None
    a['info']=u['info'] if u else ''
    if a['ll'] is None:
        xs=[p[0] for p in a['poly']];ys=[p[1] for p in a['poly']]
        a['ll']=[sum(ys)/len(ys),sum(xs)/len(xs)]
    print(a['tipo'],'|',a['nome'],'->',a['unidade'],len(a['ruas']),'ruas')

# street index
idx={}
for i,a in enumerate(areas):
    for r in a['ruas']:
        k=norm(r)
        if len(k)<2: continue
        idx.setdefault(k,{'label':r,'areas':[]})
        if i not in idx[k]['areas']: idx[k]['areas'].append(i)
print('ruas unicas mapeadas:',len(idx))

# OSM diff
known=set(idx)
faltantes=[]
for s in osm:
    k=norm(s)
    if len(k)<2: continue
    if k in known: continue
    # fuzzy: contained
    hit=any(k==x or (len(k)>6 and (k in x or x in k)) for x in known)
    if not hit: faltantes.append(s)
print('OSM total',len(osm),'faltantes',len(faltantes))
geo=json.load(open('osm_geo.json',encoding='utf-8'))
def inside(pt,poly):
    x,y=pt; c=False; n=len(poly)
    for i in range(n):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
        if ((y1>y)!=(y2>y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1): c=not c
    return c
def dist(a,b):
    import math
    dx=(a[1]-b[1])*math.cos(math.radians((a[0]+b[0])/2)); dy=a[0]-b[0]
    return math.hypot(dx,dy)*111.32
falt=[]
IGNORE=re.compile(r'(?i)^(ciclovia|freeway|rodovia|pp-|acesso |trecho|ligacao|via de|alca)')
for s_ in sorted(faltantes):
    g=geo.get(s_,{}); ll=[g.get('lat'),g.get('lon')] if g.get('lat') else None
    sug=None; d_=None
    if ll:
        for a in areas:
            if inside([ll[1],ll[0]],a['poly']): sug=a['nome']; break
        if not sug:
            b=min(areas,key=lambda a: dist(ll,a['ll'])); sug=b['nome']+' (fora das áreas – mais próxima)'
        d_=round(min(dist(ll,a['ll']) for a in areas),2)
    falt.append({'rua':s_,'lat':ll[0] if ll else None,'lon':ll[1] if ll else None,'tipo_via':g.get('hw'),
                 'sugestao':sug,'via_publica': not bool(IGNORE.match(s_))})
json.dump({'faltantes_det':falt,'areas':areas,'unidades':units,'indice':idx,'faltantes':sorted(faltantes)},open('app_data.json','w',encoding='utf-8'),ensure_ascii=False)
