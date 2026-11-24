import json, glob, os, sys, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from astropy.io import fits; from astropy.wcs import WCS
tr=[t for t in json.load(open('results/tracklets_classified.json')) if t['class']==sys.argv[1]]
os.makedirs('results/review',exist_ok=True)
for p in range(0,len(tr),8):
    sub=tr[p:p+8]
    fig,axs=plt.subplots(len(sub),5,figsize=(11,2.3*len(sub)),squeeze=False)
    for r,t in enumerate(sub):
        fs=sorted(glob.glob(os.path.dirname(t['files'][0])+'/*.fit'))
        i0=fs.index(t['files'][0]); i1=fs.index(t['files'][-1])
        ra,dec=WCS(fits.getheader(t['files'][0])).all_pix2world(t['xs'][0],t['ys'][0],0)
        for c,j in enumerate(np.linspace(i0,i1,5).astype(int)):
            x,y=WCS(fits.getheader(fs[j])).all_world2pix(ra,dec,0); x,y=int(x),int(y)
            d=fits.getdata(fs[j]).astype(np.float32)
            d=d[max(0,y-45):y+45,max(0,x-45):x+45]; d=d[0::2,0::2]+d[0::2,1::2]+d[1::2,0::2]+d[1::2,1::2] if d.shape[0]%2==0 and d.shape[1]%2==0 else d
            m=np.median(d); s=np.median(abs(d-m))*1.48+1
            ax=axs[r,c]; ax.imshow(np.arcsinh((d-m)/(3*s)),cmap='gray',origin='lower',vmin=-.5,vmax=4)
            hh,ww=d.shape; ax.axvline(ww/2,color='r',lw=.4,alpha=.6); ax.axhline(hh/2,color='r',lw=.4,alpha=.6)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title((f"{t['id']} {t['target'][:10]} {t['rate_arcsec_min']:.2f}\"/m n={t['n']} | " if c==0 else '')+os.path.basename(fs[j])[-22:-4],fontsize=6)
    plt.tight_layout(); plt.savefig(f'results/review/{sys.argv[1]}_{p//8}.png',dpi=72); plt.close()
print(len(tr))
