import os, pymupdf, sys
HERE = os.path.dirname(os.path.abspath(__file__))
def audit(path,label):
    d=pymupdf.open(path); tot=0
    print('==',label,len(d),'pages')
    for pno,p in enumerate(d,1):
        W,H=p.rect.width,p.rect.height; m=W*0.030
        spans=[s for b in p.get_text('dict')['blocks'] for l in b.get('lines',[])
                 for s in l['spans'] if s['text'].strip()]
        off=[s for s in spans if s['bbox'][0]<m-1 or s['bbox'][2]>W-m+1
                              or s['bbox'][1]<m-1 or s['bbox'][3]>H-m+1]
        bb=[s['bbox'] for s in spans]; ov=0
        for i in range(len(bb)):
            for j in range(i+1,len(bb)):
                a,c=bb[i],bb[j]
                ix=min(a[2],c[2])-max(a[0],c[0]); iy=min(a[3],c[3])-max(a[1],c[1])
                if ix>1 and iy>1:
                    amin=min((a[2]-a[0])*(a[3]-a[1]),(c[2]-c[0])*(c[3]-c[1]))
                    if amin>0 and ix*iy/amin>0.30: ov+=1
        flag='' if not(off or ov) else '  <-- FIX'
        print('  p%02d spans=%3d off=%2d overlap=%2d%s'%(pno,len(spans),len(off),ov,flag))
        for s in off[:4]: print('      OFF',repr(s['text'][:38]),[round(v) for v in s['bbox']])
        tot+=len(off)+ov
    print('  TOTAL',tot); return tot
t=audit(os.path.join(HERE,'out/a0-boards.pdf'),'A0')+audit(os.path.join(HERE,'out/a3-booklet.pdf'),'A3')
print('\nGRAND TOTAL',t)
