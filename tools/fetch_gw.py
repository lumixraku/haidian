import json,urllib.request,urllib.parse,time,os
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)
BB="39.925,116.295,40.045,116.385"
Q={
 "green":'(way["leisure"="park"](%s);way["landuse"~"^(grass|forest|recreation_ground)$"](%s););out geom tags;'%(BB,BB),
 "water":'(way["natural"="water"](%s);way["waterway"="river"](%s););out geom tags;'%(BB,BB),
}
for name,body in Q.items():
    out=os.path.join(DATA,"osm_%s.json"%name)
    if os.path.exists(out): continue
    for a in range(6):
        time.sleep(30)
        try:
            d=urllib.parse.urlencode({'data':"[out:json][timeout:120];"+body}).encode()
            r=urllib.request.Request('https://overpass-api.de/api/interpreter',data=d,headers={'User-Agent':'urban-plan/1.0'})
            j=json.load(urllib.request.urlopen(r,timeout=180))
            json.dump(j,open(out,'w'),ensure_ascii=False)
            print(name,'ok',len(j.get('elements',[]))); break
        except Exception as e:
            print(name,'retry',a,type(e).__name__,flush=True)
    else: print(name,'FAILED - proceeding without it')
