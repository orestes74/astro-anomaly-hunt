import json, sys, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from astropy.io import fits
def sp(path):
    d=fits.getdata(path).astype(np.float32); return d[0::2,0::2]+d[0::2,1::2]+d[1::2,0::2]+d[1::2,1::2]
def crop(img,x,y,h=30):
    cx,cy=int((x-.5)/2),int((y-.5)/2); c=img[max(0,cy-h):cy+h,max(0,cx-h):cx+h]
    m=np.median(c); s=np.median(abs(c-m))*1.48+1; return np.arcsinh((c-m)/(3*s))
def panel(evs, out, files_by_seq=None):
    import glob, os
    fig,axs=plt.subplots(len(evs),3,figsize=(6,2*len(evs)))
    for r,e in enumerate(evs):
        d=os.path.dirname(e['file']); fs=sorted(glob.glob(d+'/*.fit')); i=fs.index(e['file'])
        for c,j in enumerate((i-1,i,i+1)):
            ax=axs[r,c]; ax.set_xticks([]); ax.set_yticks([])
            if 0<=j<len(fs):
                ax.imshow(crop(sp(fs[j]),e['x'],e['y']),cmap='gray',origin='lower',vmin=-.5,vmax=4)
            if c==1: ax.set_title(f"{e['target']} snr{e['snr']:.0f} {os.path.basename(e['file'])[-22:-4]}",fontsize=6)
    fig.tight_layout(); fig.savefig(out,dpi=90); plt.close(fig)
if __name__=='__main__':
    ev=json.load(open('results/events.json'))
    fl=sorted([e for e in ev if e['kind']=='flash'],key=lambda e:-e['snr'])
    panel(fl[:6],'results/flash_check_top.png')
    import random; random.seed(0)
    panel(random.sample(fl,6),'results/flash_check_random.png')
