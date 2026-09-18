import re, json, xml.etree.ElementTree as ET
NS={'k':'http://www.opengis.net/kml/2.2'}
t=ET.parse('cach.kml'); r=t.getroot()
doc=r.find('k:Document',NS)
out={}
def coords(txt):
    pts=[]
    for tok in txt.split():
        p=tok.split(',')
        if len(p)>=2: pts.append([float(p[0]),float(p[1])])
    return pts
for f in doc.findall('k:Folder',NS):
    fname=f.find('k:name',NS).text.strip()
    items=[]
    for pm in f.findall('k:Placemark',NS):
        nm=(pm.find('k:name',NS).text or '').strip()
        d=pm.find('k:description',NS)
        desc=d.text if d is not None and d.text else ''
        pt=pm.find('.//k:Point/k:coordinates',NS)
        pg=pm.find('.//k:Polygon/k:outerBoundaryIs/k:LinearRing/k:coordinates',NS)
        it={'name':nm,'desc':desc}
        if pt is not None: it['point']=coords(pt.text)[0]
        if pg is not None: it['poly']=coords(pg.text)
        items.append(it)
    out[fname]=items
json.dump(out,open('data.json','w',encoding='utf-8'),ensure_ascii=False)
for k,v in out.items():
    print(k, len(v))
    for i in v:
        print('   ', repr(i['name']), 'pt' if 'point' in i else '', ('poly%d'%len(i['poly'])) if 'poly' in i else '', 'desc:%d'%len(i['desc']))
