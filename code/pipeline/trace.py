import link, csv, numpy as np, sys
from verify import skybot
cats=link.load(); seqs=link.sequences(cats)
rows={r['start']:r for r in csv.DictReader(open('results/sequences.csv',encoding='utf-8'))}
def trace(target, n, name):
    s=[s for s in seqs if s[0]['target']==target and len(s)==n][0]
    r=rows[s[0]['path']]; fl=s[0]['focallen']
    hw=6248*3.76/fl*206.265/3600/2*.95; hh=4176*3.76/fl*206.265/3600/2*.95
    mjd=(float(r['mjd0'])+float(r['mjd1']))/2
    k=[x for x in skybot(float(r['ra0']),float(r['dec0']),mjd,float(np.hypot(hw,hh))) if name in x['name']][0]
    print(name, 'V',k['V'], s[0]['path'][-45:], 'gaps(min)', np.round(np.diff([c['mjd'] for c in s])*1440,1))
    for c in s:
        dt=(c['mjd']-mjd)*24
        kra=k['ra']+k['dra']*dt/3600/np.cos(np.radians(k['dec'])); kde=k['dec']+k['ddec']*dt/3600
        d=np.hypot((c['ra']-kra)*np.cos(np.radians(kde)),c['dec']-kde)*3600
        i=np.nanargmin(d)
        print(' ',round(d[i],1), 'x,y',round(float(c['x'][i])),round(float(c['y'][i])), 'snr',round(float(c['peak'][i]/c['rms'])), 'sat',bool(c['sat'][i]), 'a,b',round(float(c['a'][i]),2),round(float(c['b'][i]),2), 'W,H', c['W'], c['H'])
trace(sys.argv[1], int(sys.argv[2]), sys.argv[3])
