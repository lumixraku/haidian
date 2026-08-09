import json,urllib.request,urllib.parse,time,os
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)
BB="39.925,116.295,40.045,116.385"
QUERIES={
 "roads":'way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"](%s);out geom tags;'%BB,
 "rail":'way["railway"~"^(rail|subway|light_rail)$"](%s);out geom tags;'%BB,
 "green":'(way["leisure"="park"](%s);way["landuse"~"^(grass|forest|recreation_ground)$"](%s););out geom tags;'%(BB,BB),
 "water":'(way["natural"="water"](%s);way["waterway"="river"](%s););out geom tags;'%(BB,BB),
}
for name,body in QUERIES.items():
    out=os.path.join(DATA,"osm_%s.json"%name)
    if os.path.exists(out): print('skip',name); continue
    q="[out:json][timeout:180];%s"%body
    for a in range(4):
        try:
            d=urllib.parse.urlencode({'data':q}).encode()
            r=urllib.request.Request('https://overpass-api.de/api/interpreter',data=d,headers={'User-Agent':'urban-plan/1.0'})
            j=json.load(urllib.request.urlopen(r,timeout=240))
            json.dump(j,open(out,'w'),ensure_ascii=False)
            print(name,len(j.get('elements',[]))); break
        except Exception as e:
            print(name,'retry',a,type(e).__name__); time.sleep(25)
    else: print(name,'FAILED')
