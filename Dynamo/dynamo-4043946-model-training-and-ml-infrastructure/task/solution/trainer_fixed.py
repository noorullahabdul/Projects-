#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np

REQ = ['data_path','seed','epochs','microbatch_size','accum_steps','dropout_p','base_lr','warmup_updates','clip_norm','beta1','beta2','adam_eps','weight_decay']

def fail(msg):
    raise ValueError(msg)

def load_validate(config_path):
    cfg=json.loads(Path(config_path).read_text())
    if any(k not in cfg for k in REQ): fail('missing config key')
    if type(cfg['seed']) is not int or type(cfg['epochs']) is not int or cfg['epochs']<=0: fail('bad seed/epochs')
    for k in ('microbatch_size','accum_steps'):
        if type(cfg[k]) is not int or cfg[k]<=0: fail('bad '+k)
    for k in ('dropout_p','base_lr','clip_norm','beta1','beta2','adam_eps','weight_decay'):
        if isinstance(cfg[k],bool) or not isinstance(cfg[k],(int,float)) or not np.isfinite(float(cfg[k])): fail('bad '+k)
    if not (0<=cfg['dropout_p']<1): fail('bad dropout')
    if cfg['base_lr']<=0 or cfg['clip_norm']<=0 or cfg['adam_eps']<=0 or cfg['weight_decay']<0: fail('bad positive config')
    if not (0<=cfg['beta1']<1 and 0<=cfg['beta2']<1): fail('bad beta')
    if type(cfg['warmup_updates']) is not int or cfg['warmup_updates']<0: fail('bad warmup')
    with np.load(cfg['data_path'], allow_pickle=False) as d:
        if not {'x','y','mask'}.issubset(set(d.files)): fail('bad dataset keys')
        x_raw=np.asarray(d['x']); y=np.asarray(d['y']); mask=np.asarray(d['mask'])
        if not (np.issubdtype(x_raw.dtype,np.integer) or np.issubdtype(x_raw.dtype,np.floating)): fail('bad x dtype')
        x=np.asarray(x_raw,dtype=np.float64)
    if x.ndim!=3 or y.shape!=x.shape[:2] or mask.shape!=x.shape[:2]: fail('bad shapes')
    if x.shape[0]==0 or x.shape[1]==0 or x.shape[2]==0 or not np.isfinite(x).all(): fail('bad x')
    if not np.issubdtype(y.dtype,np.integer): fail('bad y dtype')
    if not (np.issubdtype(mask.dtype,np.number) or np.issubdtype(mask.dtype,np.bool_)): fail('bad mask dtype')
    valid=mask!=0
    if not valid.any() or np.any(valid.sum(axis=1)==0): fail('each example needs a valid token')
    C=int(y[valid].max())+1
    if C<=0 or (y[valid]<0).any() or (y[valid]>=C).any(): fail('bad labels')
    return cfg,x,y.astype(np.int64),mask,C

def total_updates(cfg,n):
    mb=math.ceil(n/cfg['microbatch_size'])
    return cfg['epochs']*math.ceil(mb/cfg['accum_steps'])

def lr_for(cfg,u,U):
    w=cfg['warmup_updates']
    if w>=U: fail('warmup must be < total updates')
    if u<w:
        factor=(u+1)/w
    else:
        factor=(U-u)/(U-w)
    return float(cfg['base_lr']*factor)

def sum_loss_grad(x,y,mask,W,b):
    logits=x@W+b
    logits-=np.max(logits,axis=-1,keepdims=True)
    ex=np.exp(logits); p=ex/np.sum(ex,axis=-1,keepdims=True)
    valid=mask!=0; idx=np.where(valid); n=len(idx[0])
    if n==0: return 0.0,np.zeros_like(W),np.zeros_like(b),0
    probs=p[idx[0],idx[1],y[idx]]
    loss=float((-np.log(probs)).sum())
    d=p.copy(); d[idx[0],idx[1],y[idx]]-=1.0; d[~valid]=0.0
    gW=np.einsum('ntd,ntc->dc',x,d); gb=d.sum(axis=(0,1))
    return loss,gW,gb,n

def atomic_npz(path, **arrs):
    path=Path(path); tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as f: np.savez(f,**arrs)
    tmp.replace(path)

def save_checkpoint(path,state):
    # JSON-serialize non-array state; numeric arrays remain native.
    meta={k:v for k,v in state.items() if k not in {'W','b','mW','vW','mb','vb','gWa','gba','perm'}}
    atomic_npz(path,W=state['W'],b=state['b'],mW=state['mW'],vW=state['vW'],mb=state['mb'],vb=state['vb'],gWa=state['gWa'],gba=state['gba'],perm=state['perm'],meta=np.array(json.dumps(meta),dtype=np.str_))

def load_checkpoint(path):
    with np.load(path,allow_pickle=False) as d:
        meta=json.loads(str(d['meta']))
        st=dict(meta)
        for k in ('W','b','mW','vW','mb','vb','gWa','gba','perm'): st[k]=d[k].copy()
    return st

def write_trace(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='\n') as f:
        for r in rows: f.write(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n')

def write_summary(path,cfg,status,gmb,upd,last):
    obj={'schema':'resume-train/1','status':status,'seed':cfg['seed'],'epochs':cfg['epochs'],'global_microbatches':gmb,'optimizer_updates':upd,'final_loss':last}
    Path(path).write_text(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); ap.add_argument('--out',required=True); ap.add_argument('--resume'); ap.add_argument('--stop-after-microbatch',type=int)
    a=ap.parse_args()
    if a.stop_after_microbatch is not None and a.stop_after_microbatch<=0: fail('stop must be positive')
    cfg,x,y,mask,C=load_validate(a.config); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    U=total_updates(cfg,len(x))
    if cfg['warmup_updates']>=U: fail('warmup')
    D=x.shape[-1]
    trace=[]
    if a.resume:
        st=load_checkpoint(a.resume)
        if st['seed']!=cfg['seed'] or st['epochs_cfg']!=cfg['epochs'] or st['n_examples']!=len(x): fail('checkpoint mismatch')
        rng=np.random.Generator(np.random.PCG64()); rng.bit_generator.state=st['rng_state']
        W,b,mW,vW,mb,vb=st['W'],st['b'],st['mW'],st['vW'],st['mb'],st['vb']
        epoch=int(st['epoch']); cursor=int(st['cursor']); perm=st['perm'].astype(np.int64)
        gWa,gba=st['gWa'],st['gba']; loss_sum=float(st['loss_sum']); valid_count=int(st['valid_count']); group_mbs=int(st['group_mbs'])
        global_mb=int(st['global_mb']); update=int(st['update']); last_loss=st['last_loss']
    else:
        rng=np.random.Generator(np.random.PCG64(cfg['seed']))
        W=rng.normal(0.0,0.05,size=(D,C)); b=np.zeros(C,dtype=np.float64)
        mW=np.zeros_like(W); vW=np.zeros_like(W); mb=np.zeros_like(b); vb=np.zeros_like(b)
        epoch=0; cursor=0; perm=np.empty(0,dtype=np.int64)
        gWa=np.zeros_like(W); gba=np.zeros_like(b); loss_sum=0.0; valid_count=0; group_mbs=0; global_mb=0; update=0; last_loss=None
    while epoch<cfg['epochs']:
        if cursor==0 and len(perm)==0:
            perm=rng.permutation(len(x))
        while cursor<len(x):
            ii=perm[cursor:cursor+cfg['microbatch_size']]; cursor+=len(ii)
            xb=x[ii].copy(); yb=y[ii]; mk=mask[ii]
            p=cfg['dropout_p']
            if p>0:
                r=rng.random(xb.shape); xb=xb*(r>=p)/(1-p)
            ls,gW,gb,n=sum_loss_grad(xb,yb,mk,W,b)
            gWa+=gW; gba+=gb; loss_sum+=ls; valid_count+=n; group_mbs+=1; global_mb+=1
            end_epoch=cursor>=len(x)
            if group_mbs==cfg['accum_steps'] or end_epoch:
                if valid_count>0:
                    gWn=gWa/valid_count; gbn=gba/valid_count; avg_loss=loss_sum/valid_count
                    gn=float(np.sqrt(np.sum(gWn*gWn)+np.sum(gbn*gbn)))
                    clipped=gn>cfg['clip_norm']
                    if clipped:
                        sc=cfg['clip_norm']/gn; gWn*=sc; gbn*=sc
                    gpost=float(np.sqrt(np.sum(gWn*gWn)+np.sum(gbn*gbn)))
                    u=update; lr=lr_for(cfg,u,U); t=u+1
                    mW=cfg['beta1']*mW+(1-cfg['beta1'])*gWn; vW=cfg['beta2']*vW+(1-cfg['beta2'])*(gWn*gWn)
                    mb=cfg['beta1']*mb+(1-cfg['beta1'])*gbn; vb=cfg['beta2']*vb+(1-cfg['beta2'])*(gbn*gbn)
                    mWh=mW/(1-cfg['beta1']**t); vWh=vW/(1-cfg['beta2']**t); mbh=mb/(1-cfg['beta1']**t); vbh=vb/(1-cfg['beta2']**t)
                    W=W-lr*(mWh/(np.sqrt(vWh)+cfg['adam_eps'])+cfg['weight_decay']*W)
                    b=b-lr*(mbh/(np.sqrt(vbh)+cfg['adam_eps'])+cfg['weight_decay']*b)
                    update+=1; last_loss=float(avg_loss)
                    trace.append({'update':update,'epoch':epoch+1,'group_microbatches':group_mbs,'global_microbatch':global_mb,'valid_tokens':valid_count,'lr':lr,'loss':float(avg_loss),'grad_norm_preclip':gn,'grad_norm_postclip':gpost,'clipped':bool(clipped)})
                gWa=np.zeros_like(W); gba=np.zeros_like(b); loss_sum=0.0; valid_count=0; group_mbs=0
            if a.stop_after_microbatch is not None and global_mb==a.stop_after_microbatch:
                # Preserve current epoch permutation and next cursor, including pending group.
                state=dict(W=W,b=b,mW=mW,vW=vW,mb=mb,vb=vb,gWa=gWa,gba=gba,perm=perm,seed=cfg['seed'],epochs_cfg=cfg['epochs'],n_examples=len(x),rng_state=rng.bit_generator.state,epoch=epoch,cursor=cursor,loss_sum=loss_sum,valid_count=valid_count,group_mbs=group_mbs,global_mb=global_mb,update=update,last_loss=last_loss)
                save_checkpoint(out/'checkpoint.npz',state); write_trace(out/'train_trace.jsonl',trace); write_summary(out/'summary.json',cfg,'paused',global_mb,update,last_loss)
                try: (out/'final_state.npz').unlink()
                except FileNotFoundError: pass
                return
        epoch+=1; cursor=0; perm=np.empty(0,dtype=np.int64)
    write_trace(out/'train_trace.jsonl',trace); atomic_npz(out/'final_state.npz',W=W,b=b,m_W=mW,v_W=vW,m_b=mb,v_b=vb); write_summary(out/'summary.json',cfg,'completed',global_mb,update,last_loss)

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(f'error: {e}',file=__import__('sys').stderr); raise SystemExit(2)
