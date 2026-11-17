"""Phan tich ro ri. Chay: SCR=... python -I leak_analyze.py"""
import os, numpy as np, csv
SCR=os.environ['SCR']; OUT='/mnt/d/Personal/Drone-Tracking/vision/results/verify'
L={sp:np.load(f'{SCR}/feat_{sp}.npz') for sp in ('train','val','test')}
def norm(F):
    F=F-F.mean(1,keepdims=True); return F/np.maximum(np.linalg.norm(F,axis=1,keepdims=True),1e-6)
N={sp:norm(L[sp]['F']) for sp in L}
S={sp:L[sp]['stems'] for sp in L}
# 1) thu tu: tuong quan anh i voi i+1 so voi cap ngau nhien
rng=np.random.default_rng(0)
for sp in ('train','val','test'):
    X=N[sp]; adj=(X[:-1]*X[1:]).sum(1)
    a=rng.integers(0,len(X),5000); b=rng.integers(0,len(X),5000); m=a!=b
    rnd=(X[a[m]]*X[b[m]]).sum(1)
    print(f'[thu tu] {sp}: tuong quan i~i+1 trung vi {np.median(adj):.3f}, ti le>=0.9 {np.mean(adj>=0.9):.3f}; cap ngau nhien trung vi {np.median(rnd):.3f}, ti le>=0.9 {np.mean(rnd>=0.9):.4f}')
# tap con V1 da dung
used={}
for sp in ('train','val'):
    d=f'/mnt/d/Personal/Drone-Tracking/vision/data/dut-train/images/{sp}'
    used[sp]=sorted({f[:-4].split('_',1)[1] for f in os.listdir(d)})
    print(f'[tap con V1] {sp}: {len(used[sp])} anh goc khac nhau')
idx_used=np.isin(S['train'],used['train'])
T=N['test']
def nn(Q,R,excl_self=False):
    C=Q@R.T
    if excl_self: np.fill_diagonal(C,-2)
    j=C.argmax(1); return C[np.arange(len(Q)),j],j
c_tr,j_tr=nn(T,N['train'])
c_us,j_us=nn(T,N['train'][idx_used]); j_us=np.where(idx_used)[0][j_us]
c_va,j_va=nn(T,N['val'])
c_te,j_te=nn(T,T,True)
c_tt,_=nn(N['train'],N['train'],True)
# dHash
def ham(Q,R):
    Qi=Q.astype(np.int8)*2-1; Ri=R.astype(np.int8)*2-1
    return (64-(Qi@Ri.T.astype(np.int16)))//2  # so bit khac
Hm=ham(L['test']['H'],L['train']['H']).astype(int); h_tr=Hm.min(1); hj=Hm.argmin(1)
qs=[0,5,25,50,75,95,100]
for nm,c in (('test->train',c_tr),('test->tap con V1',c_us),('test->val',c_va),('test->test(khac)',c_te),('train->train(khac)',c_tt)):
    print(f'[tuong quan gan nhat] {nm}: phan vi {qs} = {np.round(np.percentile(c,qs),3).tolist()}')
print('[hamming dHash nho nhat test->train] phan vi',qs,np.percentile(h_tr,qs).tolist())
for th in (0.8,0.9,0.95,0.98):
    print(f'[ti le test co anh gan trung] corr>={th}: train {np.mean(c_tr>=th):.3f} | tap con V1 {np.mean(c_us>=th):.3f} | val {np.mean(c_va>=th):.3f} | trong test {np.mean(c_te>=th):.3f}')
for th in (4,8,12):
    print(f'[dHash] hamming<={th}: {np.mean(h_tr<=th):.3f}')
with open(f'{OUT}/leak_test_vs_train.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['test_stem','corr_train','train_stem','dhash_ham_train','dhash_train_stem','corr_v1subset','v1subset_train_stem','corr_val','val_stem'])
    for i in range(len(T)):
        w.writerow([S['test'][i],f'{c_tr[i]:.4f}',S['train'][j_tr[i]],h_tr[i],S['train'][hj[i]],f'{c_us[i]:.4f}',S['train'][j_us[i]],f'{c_va[i]:.4f}',S['val'][j_va[i]]])
# vi du theo muc tuong quan
for lo,hi in ((0.99,1.01),(0.95,0.99),(0.9,0.95),(0.8,0.9),(0.6,0.8)):
    ii=np.where((c_tr>=lo)&(c_tr<hi))[0]; print(f'[vi du corr {lo}-{hi}] n={len(ii)}', [(S["test"][i],S["train"][j_tr[i]],round(float(c_tr[i]),3)) for i in ii[:4]])