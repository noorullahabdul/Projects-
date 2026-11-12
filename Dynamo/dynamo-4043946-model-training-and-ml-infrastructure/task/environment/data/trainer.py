#!/usr/bin/env python3
"""Intentionally buggy training loop. Repair it to satisfy TRAINING_SPEC.md."""
import argparse, json
from pathlib import Path
import numpy as np


def load_config(path):
    return json.loads(Path(path).read_text())


def softmax_ce_and_grad(x, y, mask, W, b):
    logits = x @ W + b
    logits = logits - np.max(logits, axis=-1, keepdims=True)
    p = np.exp(logits); p /= np.sum(p, axis=-1, keepdims=True)
    valid = mask != 0
    idx = np.where(valid)
    if len(idx[0]) == 0:
        return 0.0, np.zeros_like(W), np.zeros_like(b), 0
    loss = -np.log(np.maximum(p[idx[0], idx[1], y[idx]], 1e-300)).mean()
    d = p.copy()
    d[idx[0], idx[1], y[idx]] -= 1.0
    d[~valid] = 0.0
    d /= len(idx[0])
    gW = np.einsum('ntd,ntc->dc', x, d)
    gb = d.sum(axis=(0,1))
    return float(loss), gW, gb, len(idx[0])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--config',required=True); ap.add_argument('--out',required=True)
    ap.add_argument('--resume'); ap.add_argument('--stop-after-microbatch',type=int)
    a=ap.parse_args(); cfg=load_config(a.config); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    data=np.load(cfg['data_path']); x=data['x'].astype(float); y=data['y']; mask=data['mask']
    C=int(y[mask!=0].max())+1; D=x.shape[-1]
    rs=np.random.RandomState(cfg['seed'])
    W=rs.normal(0,0.05,size=(D,C)); b=np.zeros(C)
    mW=np.zeros_like(W); vW=np.zeros_like(W); mb=np.zeros_like(b); vb=np.zeros_like(b)
    start_epoch=0; global_mb=0; update=0
    if a.resume:
        cp=np.load(a.resume)
        W=cp['W']; b=cp['b']
        global_mb=int(cp['global_mb']) if 'global_mb' in cp else 0
    trace=[]
    for epoch in range(start_epoch,cfg['epochs']):
        perm=rs.permutation(len(x))
        gWa=np.zeros_like(W); gba=np.zeros_like(b); ngrp=0; losses=[]; valids=0
        for s in range(0,len(x),cfg['microbatch_size']):
            ii=perm[s:s+cfg['microbatch_size']]; xb=x[ii].copy(); yb=y[ii]; mk=mask[ii]
            if cfg['dropout_p']>0:
                keep=(rs.rand(*xb.shape)>=cfg['dropout_p'])
                xb=xb*keep/(1-cfg['dropout_p'])
            loss,gW,gb,n=softmax_ce_and_grad(xb,yb,mk,W,b)
            gn=float(np.sqrt((gW*gW).sum()+(gb*gb).sum()))
            if gn>cfg['clip_norm'] and gn>0:
                sc=cfg['clip_norm']/gn; gW*=sc; gb*=sc
            gWa+=gW; gba+=gb; ngrp+=1; losses.append(loss); valids+=n
            global_mb+=1
            if ngrp==cfg['accum_steps']:
                gWa/=cfg['accum_steps']; gba/=cfg['accum_steps']
                update+=1; lr=cfg['base_lr']*max(0.05,1-global_mb/100.0)
                mW=cfg['beta1']*mW+(1-cfg['beta1'])*gWa; vW=cfg['beta2']*vW+(1-cfg['beta2'])*(gWa*gWa)
                mb=cfg['beta1']*mb+(1-cfg['beta1'])*gba; vb=cfg['beta2']*vb+(1-cfg['beta2'])*(gba*gba)
                W-=lr*(mW/(np.sqrt(vW)+cfg['adam_eps'])+cfg['weight_decay']*W)
                b-=lr*(mb/(np.sqrt(vb)+cfg['adam_eps'])+cfg['weight_decay']*b)
                trace.append({'update':update,'epoch':epoch+1,'group_microbatches':ngrp,'global_microbatch':global_mb,'valid_tokens':valids,'lr':lr,'loss':float(np.mean(losses)),'grad_norm_preclip':gn,'grad_norm_postclip':min(gn,cfg['clip_norm']),'clipped':bool(gn>cfg['clip_norm'])})
                gWa.fill(0); gba.fill(0); ngrp=0; losses=[]; valids=0
            if a.stop_after_microbatch and global_mb>=a.stop_after_microbatch:
                np.savez(out/'checkpoint.npz',W=W,b=b,global_mb=global_mb)
                (out/'summary.json').write_text(json.dumps({'schema':'resume-train/1','status':'paused','seed':cfg['seed'],'epochs':cfg['epochs'],'global_microbatches':global_mb,'optimizer_updates':update,'final_loss':trace[-1]['loss'] if trace else None})+'\n')
                with (out/'train_trace.jsonl').open('w') as f:
                    for r in trace: f.write(json.dumps(r)+'\n')
                return
    with (out/'train_trace.jsonl').open('w') as f:
        for r in trace: f.write(json.dumps(r)+'\n')
    np.savez(out/'final_state.npz',W=W,b=b,m_W=mW,v_W=vW,m_b=mb,v_b=vb)
    (out/'summary.json').write_text(json.dumps({'schema':'resume-train/1','status':'completed','seed':cfg['seed'],'epochs':cfg['epochs'],'global_microbatches':global_mb,'optimizer_updates':update,'final_loss':trace[-1]['loss'] if trace else None})+'\n')

if __name__=='__main__': main()
