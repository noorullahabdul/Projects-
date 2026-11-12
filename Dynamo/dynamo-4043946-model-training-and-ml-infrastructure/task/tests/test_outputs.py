import json, math, os, subprocess, tempfile, hashlib
from pathlib import Path
import numpy as np
import pytest

APP=Path('/app'); TRAINER=APP/'trainer.py'; SPEC=APP/'TRAINING_SPEC.md'; BASE_CONFIG=APP/'config.json'; BASE_DATA=APP/'data/train.npz'
TRACE_KEYS={'update','epoch','group_microbatches','global_microbatch','valid_tokens','lr','loss','grad_norm_preclip','grad_norm_postclip','clipped'}
SUMMARY_KEYS={'schema','status','seed','epochs','global_microbatches','optimizer_updates','final_loss'}
STATE_KEYS={'W','b','m_W','v_W','m_b','v_b'}
CANONICAL_VISIBLE_SHA256={
    BASE_CONFIG:'98fbefffad81d084c5d9da055571d41c71cb1e5b839e1148014fac5ccfe46262',
    BASE_DATA:'3face0fab7f88048b4f9b683db00bee5458bc11b6bcd8130ced7483a2cb25014',
    SPEC:'ddd185e055ebeafdcfe7ce13c89d0fdabd78c255ccdfd0c62228709498bc3348',
}

def run(config,out,resume=None,stop=None,check=True):
    cmd=['python3',str(TRAINER),'--config',str(config),'--out',str(out)]
    if resume is not None: cmd += ['--resume',str(resume)]
    if stop is not None: cmd += ['--stop-after-microbatch',str(stop)]
    env=os.environ.copy(); env['OPENBLAS_NUM_THREADS']='1'; env['OMP_NUM_THREADS']='1'; env['MKL_NUM_THREADS']='1'
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=30,env=env)
    if check and p.returncode!=0: raise AssertionError(f'command failed: {p.returncode}\nstdout={p.stdout}\nstderr={p.stderr}')
    return p

def load_trace(out):
    p=Path(out)/'train_trace.jsonl'
    rows=[]
    for line in p.read_text().splitlines():
        obj=json.loads(line); assert set(obj)==TRACE_KEYS; rows.append(obj)
    return rows

def load_state(out):
    with np.load(Path(out)/'final_state.npz',allow_pickle=False) as d:
        assert set(d.files)==STATE_KEYS
        state={k:d[k].copy() for k in d.files}
    assert all(np.isfinite(v).all() for v in state.values())
    return state

def contract_for_config(config_path):
    cfg=json.loads(Path(config_path).read_text())
    with np.load(cfg['data_path'],allow_pickle=False) as d:
        x=np.asarray(d['x']); y=np.asarray(d['y']); mask=np.asarray(d['mask'])
    D=x.shape[-1]; C=int(y[mask!=0].max())+1; n=x.shape[0]
    global_mbs=cfg['epochs']*math.ceil(n/cfg['microbatch_size'])
    return cfg,D,C,global_mbs

def visible_contract():
    return contract_for_config(BASE_CONFIG)

def assert_state_shapes(state,D,C):
    assert state['W'].shape==(D,C)
    assert state['m_W'].shape==(D,C)
    assert state['v_W'].shape==(D,C)
    assert state['b'].shape==(C,)
    assert state['m_b'].shape==(C,)
    assert state['v_b'].shape==(C,)

def assert_completed_summary(out,cfg,rows,global_microbatches):
    s=json.loads((Path(out)/'summary.json').read_text())
    assert set(s)==SUMMARY_KEYS
    assert s['schema']=='resume-train/1' and s['status']=='completed'
    assert s['seed']==cfg['seed'] and s['epochs']==cfg['epochs']
    assert s['global_microbatches']==global_microbatches
    assert s['optimizer_updates']==len(rows)
    assert rows and s['final_loss']==pytest.approx(rows[-1]['loss'],rel=3e-12,abs=3e-12)
    return s

def hidden_case(tmp_path,n=13,t=4,d=3,c=4,seed=99,mask_mode='varied',**overrides):
    r=np.random.default_rng(seed)
    x=r.normal(size=(n,t,d)).astype(np.float64); y=r.integers(0,c,size=(n,t),dtype=np.int64)
    if mask_mode=='varied':
        mask=(r.random((n,t))>0.42).astype(np.int64); mask[mask.sum(axis=1)==0,0]=1; mask[0,:]=1; mask[1,:]=[1]+[0]*(t-1)
    elif mask_mode=='all': mask=np.ones((n,t),dtype=np.int64)
    elif mask_mode=='no_valid_example':
        mask=np.ones((n,t),dtype=np.int64); mask[0]=0
    data=tmp_path/'data.npz'; np.savez(data,x=x,y=y,mask=mask)
    cfg=dict(data_path=str(data),seed=211,epochs=3,microbatch_size=3,accum_steps=2,dropout_p=.31,base_lr=.027,warmup_updates=2,clip_norm=.32,beta1=.81,beta2=.93,adam_eps=1e-8,weight_decay=.017)
    cfg.update(overrides); cp=tmp_path/'config.json'; cp.write_text(json.dumps(cfg)+'\n'); return cp,data,cfg

def assert_rows_close(a,b,tol=2e-12):
    assert len(a)==len(b)
    for x,y in zip(a,b):
        assert set(x)==set(y)==TRACE_KEYS
        for k in TRACE_KEYS:
            if isinstance(x[k],float) or isinstance(y[k],float): assert float(x[k])==pytest.approx(float(y[k]),rel=tol,abs=tol),k
            else: assert x[k]==y[k],k

def assert_states_close(a,b,tol=1e-12):
    assert set(a)==set(b)==STATE_KEYS
    for k in STATE_KEYS: np.testing.assert_allclose(a[k],b[k],rtol=tol,atol=tol)


def oracle_completed(config_path):
    """Independent compact reference used only by the verifier for hidden numeric cases."""
    cfg=json.loads(Path(config_path).read_text())
    with np.load(cfg['data_path'],allow_pickle=False) as d:
        x=np.asarray(d['x'],dtype=np.float64); y=np.asarray(d['y'],dtype=np.int64); mask=np.asarray(d['mask'])
    valid=mask!=0; C=int(y[valid].max())+1; D=x.shape[-1]; n=len(x)
    rng=np.random.Generator(np.random.PCG64(cfg['seed']))
    W=rng.normal(0.0,0.05,size=(D,C)); b=np.zeros(C); mW=np.zeros_like(W); vW=np.zeros_like(W); mb=np.zeros_like(b); vb=np.zeros_like(b)
    mbs_per_epoch=math.ceil(n/cfg['microbatch_size']); U=cfg['epochs']*math.ceil(mbs_per_epoch/cfg['accum_steps'])
    rows=[]; global_mb=0; upd=0
    for epoch in range(cfg['epochs']):
        perm=rng.permutation(n); gWa=np.zeros_like(W); gba=np.zeros_like(b); ls=0.0; vc=0; gm=0
        for start in range(0,n,cfg['microbatch_size']):
            ii=perm[start:start+cfg['microbatch_size']]; xb=x[ii].copy(); yb=y[ii]; mk=mask[ii]
            if cfg['dropout_p']>0:
                rr=rng.random(xb.shape); xb=xb*(rr>=cfg['dropout_p'])/(1-cfg['dropout_p'])
            logits=xb@W+b; logits-=np.max(logits,axis=-1,keepdims=True); ex=np.exp(logits); probs=ex/np.sum(ex,axis=-1,keepdims=True)
            vv=mk!=0; idx=np.where(vv); num=len(idx[0]); ls+=float((-np.log(probs[idx[0],idx[1],yb[idx]])).sum())
            dlt=probs.copy(); dlt[idx[0],idx[1],yb[idx]]-=1.0; dlt[~vv]=0.0
            gWa+=np.einsum('ntd,ntc->dc',xb,dlt); gba+=dlt.sum(axis=(0,1)); vc+=num; gm+=1; global_mb+=1
            if gm==cfg['accum_steps'] or start+cfg['microbatch_size']>=n:
                gw=gWa/vc; gb=gba/vc; loss=ls/vc; pre=float(np.sqrt(np.sum(gw*gw)+np.sum(gb*gb)))
                clipped=pre>cfg['clip_norm']
                if clipped:
                    scale=cfg['clip_norm']/pre; gw*=scale; gb*=scale
                post=float(np.sqrt(np.sum(gw*gw)+np.sum(gb*gb)))
                u=upd; warm=cfg['warmup_updates']; factor=(u+1)/warm if u<warm else (U-u)/(U-warm); lr=float(cfg['base_lr']*factor); t=u+1
                mW=cfg['beta1']*mW+(1-cfg['beta1'])*gw; vW=cfg['beta2']*vW+(1-cfg['beta2'])*(gw*gw)
                mb=cfg['beta1']*mb+(1-cfg['beta1'])*gb; vb=cfg['beta2']*vb+(1-cfg['beta2'])*(gb*gb)
                mhW=mW/(1-cfg['beta1']**t); vhW=vW/(1-cfg['beta2']**t); mhb=mb/(1-cfg['beta1']**t); vhb=vb/(1-cfg['beta2']**t)
                W=W-lr*(mhW/(np.sqrt(vhW)+cfg['adam_eps'])+cfg['weight_decay']*W); b=b-lr*(mhb/(np.sqrt(vhb)+cfg['adam_eps'])+cfg['weight_decay']*b)
                upd+=1; rows.append({'update':upd,'epoch':epoch+1,'group_microbatches':gm,'global_microbatch':global_mb,'valid_tokens':vc,'lr':lr,'loss':float(loss),'grad_norm_preclip':pre,'grad_norm_postclip':post,'clipped':bool(clipped)})
                gWa.fill(0); gba.fill(0); ls=0.0; vc=0; gm=0
    state={'W':W,'b':b,'m_W':mW,'v_W':vW,'m_b':mb,'v_b':vb}
    return rows,state


def test_required_visible_artifacts_are_genuine(tmp_path):
    """Pre-existing /app/out must be the genuine completed visible run, not schema-correct fabricated values."""
    out=APP/'out'
    assert (out/'final_state.npz').is_file()
    assert (out/'train_trace.jsonl').is_file()
    assert (out/'summary.json').is_file()
    summary_bytes=(out/'summary.json').read_bytes(); trace_bytes=(out/'train_trace.jsonl').read_bytes()
    assert summary_bytes.endswith(b'\n') and trace_bytes.endswith(b'\n')

    cfg,D,C,global_mbs=visible_contract()
    actual_rows=load_trace(out); actual_state=load_state(out)
    assert_state_shapes(actual_state,D,C)
    assert_completed_summary(out,cfg,actual_rows,global_mbs)

    # Independent verifier oracle fixes the required visible numerical result.
    exp_rows,exp_state=oracle_completed(BASE_CONFIG)
    assert_rows_close(actual_rows,exp_rows,3e-12)
    assert_states_close(actual_state,exp_state,3e-12)

    # Also prove the committed artifacts equal a fresh execution of the repaired trainer.
    fresh=tmp_path/'fresh-visible'; run(BASE_CONFIG,fresh)
    fresh_rows=load_trace(fresh); fresh_state=load_state(fresh)
    assert_rows_close(actual_rows,fresh_rows,0)
    assert_states_close(actual_state,fresh_state,0)
    assert json.loads(summary_bytes)==json.loads((fresh/'summary.json').read_text())

def test_visible_outputs_and_schema(tmp_path):
    """Visible run completes with exact schemas, summary semantics, finite arrays, and contract shapes."""
    out=tmp_path/'out'; run(BASE_CONFIG,out)
    cfg,D,C,global_mbs=visible_contract()
    rows=load_trace(out); assert rows[-1]['update']==len(rows)
    st=load_state(out); assert_state_shapes(st,D,C)
    assert_completed_summary(out,cfg,rows,global_mbs)

def test_visible_inputs_match_canonical_bytes_and_remain_unchanged(tmp_path):
    """Visible config/data/spec must equal the Docker-baked canonical bytes before and after trainer execution."""
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in CANONICAL_VISIBLE_SHA256}
    assert before==CANONICAL_VISIBLE_SHA256
    run(BASE_CONFIG,tmp_path/'out')
    after={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in CANONICAL_VISIBLE_SHA256}
    assert after==CANONICAL_VISIBLE_SHA256

def test_fresh_runs_are_deterministic(tmp_path):
    """Two fresh executions with the same seed/config/data are numerically identical."""
    a=tmp_path/'a'; b=tmp_path/'b'; run(BASE_CONFIG,a); run(BASE_CONFIG,b)
    assert_rows_close(load_trace(a),load_trace(b),0); assert_states_close(load_state(a),load_state(b),0)
    assert json.loads((a/'summary.json').read_text())==json.loads((b/'summary.json').read_text())


def test_hidden_numeric_oracle_with_dropout(tmp_path):
    """Hidden variable-mask/dropout run matches an independent oracle for initialization, masking, clipping, scheduler and AdamW math."""
    cfg,_,_=hidden_case(tmp_path,n=13,t=4,d=3,c=4,dropout_p=.31,microbatch_size=3,accum_steps=2)
    out=tmp_path/'out'; run(cfg,out); exp_rows,exp_state=oracle_completed(cfg)
    rows=load_trace(out); state=load_state(out)
    assert_rows_close(rows,exp_rows,3e-12); assert_states_close(state,exp_state,3e-12)
    c,D,C,global_mbs=contract_for_config(cfg)
    assert_state_shapes(state,D,C); assert_completed_summary(out,c,rows,global_mbs)


def test_hidden_numeric_oracle_without_dropout(tmp_path):
    """Zero-dropout hidden run catches incorrect RNG consumption and later-epoch shuffle drift."""
    cfg,_,_=hidden_case(tmp_path,n=11,t=3,d=2,c=3,dropout_p=0.0,microbatch_size=4,accum_steps=2,warmup_updates=1)
    out=tmp_path/'out'; run(cfg,out); exp_rows,exp_state=oracle_completed(cfg)
    rows=load_trace(out); state=load_state(out)
    assert_rows_close(rows,exp_rows,3e-12); assert_states_close(state,exp_state,3e-12)
    c,D,C,global_mbs=contract_for_config(cfg)
    assert_state_shapes(state,D,C); assert_completed_summary(out,c,rows,global_mbs)

def test_resume_inside_accumulation_group(tmp_path):
    """Checkpointing inside an unfinished accumulation group resumes without replay/skip/state loss."""
    cfg,_,_=hidden_case(tmp_path,n=14,microbatch_size=3,accum_steps=3)
    full=tmp_path/'full'; part=tmp_path/'part'; resumed=tmp_path/'resumed'; run(cfg,full); run(cfg,part,stop=2)
    assert (part/'checkpoint.npz').exists() and not (part/'final_state.npz').exists(); ps=json.loads((part/'summary.json').read_text()); assert ps['status']=='paused' and ps['global_microbatches']==2 and ps['optimizer_updates']==0; assert load_trace(part)==[]
    run(cfg,resumed,resume=part/'checkpoint.npz')
    combined=load_trace(part)+load_trace(resumed); assert_rows_close(combined,load_trace(full)); assert_states_close(load_state(resumed),load_state(full))

def test_resume_on_update_boundary(tmp_path):
    """Checkpoint boundary after a microbatch that triggers an update includes that update exactly once."""
    cfg,_,_=hidden_case(tmp_path,n=12,microbatch_size=2,accum_steps=2)
    full=tmp_path/'full'; part=tmp_path/'part'; resumed=tmp_path/'res'; run(cfg,full); run(cfg,part,stop=4); run(cfg,resumed,resume=part/'checkpoint.npz')
    assert len(load_trace(part))==2; assert_rows_close(load_trace(part)+load_trace(resumed),load_trace(full)); assert_states_close(load_state(resumed),load_state(full))


def test_resume_can_pause_again_at_a_global_boundary(tmp_path):
    """A resumed invocation may specify a later global stop target; progress remains global across multiple resumes."""
    cfg,_,_=hidden_case(tmp_path,n=12,t=3,d=3,c=4,epochs=2,microbatch_size=2,accum_steps=2,dropout_p=.37)
    full=tmp_path/'full'; p1=tmp_path/'p1'; p2=tmp_path/'p2'; done=tmp_path/'done'
    run(cfg,full)
    run(cfg,p1,stop=2)
    run(cfg,p2,resume=p1/'checkpoint.npz',stop=5)
    s2=json.loads((p2/'summary.json').read_text()); assert s2['status']=='paused' and s2['global_microbatches']==5
    run(cfg,done,resume=p2/'checkpoint.npz')
    combined=load_trace(p1)+load_trace(p2)+load_trace(done)
    assert_rows_close(combined,load_trace(full),2e-12)
    assert_states_close(load_state(done),load_state(full),1e-12)

def test_partial_group_flushed_and_token_weighted(tmp_path):
    """Final short accumulation groups are updated and group losses are weighted by valid-token count, not microbatch means."""
    cfg,_,c=hidden_case(tmp_path,n=10,t=5,microbatch_size=3,accum_steps=3,dropout_p=0.0,mask_mode='varied')
    out=tmp_path/'out'; run(cfg,out); rows=load_trace(out)
    mbs=math.ceil(10/3); expected=c['epochs']*math.ceil(mbs/c['accum_steps']); assert len(rows)==expected
    # each epoch has 4 microbatches => groups of 3 then 1
    assert [r['group_microbatches'] for r in rows]==[3,1]*c['epochs']
    assert all(r['valid_tokens']>0 for r in rows)

def test_scheduler_steps_per_optimizer_update(tmp_path):
    """Learning-rate schedule follows exact update-index formula, including warmup boundary."""
    cfg,_,c=hidden_case(tmp_path,n=11,microbatch_size=2,accum_steps=2,warmup_updates=2,dropout_p=0.0)
    out=tmp_path/'out'; run(cfg,out); rows=load_trace(out); U=len(rows); w=c['warmup_updates']
    exp=[]
    for u in range(U):
        factor=(u+1)/w if u<w else (U-u)/(U-w); exp.append(c['base_lr']*factor)
    np.testing.assert_allclose([r['lr'] for r in rows],exp,rtol=1e-14,atol=1e-14)


def test_softmax_is_numerically_stable_for_large_common_logits(tmp_path):
    """Large common logit offsets must stay finite, requiring the documented per-token max subtraction."""
    seed=123; D=C=3; n=3
    rng=np.random.Generator(np.random.PCG64(seed)); W0=rng.normal(0.0,0.05,size=(D,C))
    targets=np.array([[1000.0,1001.0,999.0],[999.0,1000.0,1001.0],[1001.0,999.0,1000.0]])
    x=(targets @ np.linalg.inv(W0)).reshape(n,1,D)
    y=np.array([[0],[1],[2]],dtype=np.int64); mask=np.ones((n,1),dtype=np.int64)
    data=tmp_path/'data.npz'; np.savez(data,x=x,y=y,mask=mask)
    cfg_obj=dict(data_path=str(data),seed=seed,epochs=1,microbatch_size=3,accum_steps=1,dropout_p=0.0,
                 base_lr=.001,warmup_updates=0,clip_norm=.1,beta1=.8,beta2=.9,adam_eps=1e-8,weight_decay=0.0)
    cfg=tmp_path/'config.json'; cfg.write_text(json.dumps(cfg_obj)+'\n')
    out=tmp_path/'out'; run(cfg,out)
    rows=load_trace(out); st=load_state(out); assert len(rows)==1
    assert all(math.isfinite(float(rows[0][k])) for k in ('loss','grad_norm_preclip','grad_norm_postclip','lr'))
    exp_rows,exp_state=oracle_completed(cfg)
    assert_rows_close(rows,exp_rows,3e-12); assert_states_close(st,exp_state,3e-12)

def test_global_clipping_after_accumulation(tmp_path):
    """Clipping is applied once to normalized accumulated gradients and the trace exposes the strict > decision."""
    cfg,_,c=hidden_case(tmp_path,n=9,microbatch_size=2,accum_steps=3,clip_norm=0.055,dropout_p=0.0)
    out=tmp_path/'out'; run(cfg,out); rows=load_trace(out)
    assert any(r['grad_norm_preclip']>c['clip_norm'] for r in rows)
    for r in rows:
        assert r['grad_norm_postclip']<=c['clip_norm']+1e-12
        expected=r['grad_norm_preclip']>c['clip_norm']
        assert r['clipped'] is expected
        if expected: assert r['grad_norm_postclip']==pytest.approx(c['clip_norm'],rel=1e-12,abs=1e-12)
        else: assert r['grad_norm_postclip']==pytest.approx(r['grad_norm_preclip'],rel=1e-12,abs=1e-12)


def test_clip_equality_is_observably_not_clipped(tmp_path):
    """At exact norm==clip_norm the required trace flag is false, killing > to >= boundary mutations."""
    cfg,_,_=hidden_case(tmp_path,n=4,t=3,d=2,c=3,epochs=1,microbatch_size=4,accum_steps=1,dropout_p=0.0,warmup_updates=0,clip_norm=1e6)
    probe=tmp_path/'probe'; run(cfg,probe); probe_rows=load_trace(probe)
    assert len(probe_rows)==1
    boundary=probe_rows[0]['grad_norm_preclip']; assert boundary>0
    c=json.loads(Path(cfg).read_text()); c['clip_norm']=boundary
    eq_cfg=tmp_path/'eq_config.json'; eq_cfg.write_text(json.dumps(c,separators=(',',':'))+'\n')
    out=tmp_path/'equal'; run(eq_cfg,out); rows=load_trace(out)
    assert len(rows)==1
    r=rows[0]
    assert r['grad_norm_preclip']==boundary
    assert r['clipped'] is False
    assert r['grad_norm_postclip']==r['grad_norm_preclip']


def test_nonbinary_mask_values_use_nonzero_semantics(tmp_path):
    """Any nonzero numeric mask value is valid; logic must not special-case mask==1."""
    cfg,data,_=hidden_case(tmp_path,n=8,t=4,d=3,c=4,dropout_p=.0,microbatch_size=3,accum_steps=2)
    with np.load(data,allow_pickle=False) as d:
        x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()
    nz=mask!=0
    mm=np.zeros(mask.shape,dtype=np.float64)
    rr=np.indices(mask.shape).sum(axis=0)
    mm[nz]=np.where((rr[nz]%2)==0,-2.5,3.25)
    np.savez(data,x=x,y=y,mask=mm)
    out=tmp_path/'out'; run(cfg,out)
    exp_rows,exp_state=oracle_completed(cfg)
    assert_rows_close(load_trace(out),exp_rows,3e-12)
    assert_states_close(load_state(out),exp_state,3e-12)


def test_dropout_equality_uses_greater_equal(tmp_path):
    """An RNG draw exactly equal to dropout_p is kept, distinguishing >= from > at the dropout threshold."""
    cfg,data,cfg_obj=hidden_case(tmp_path,n=4,t=2,d=2,c=3,epochs=1,microbatch_size=4,accum_steps=1,
                                 dropout_p=.2,warmup_updates=0,clip_norm=10.0,mask_mode='all')
    with np.load(data,allow_pickle=False) as d:
        x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()
    C=int(y[mask!=0].max())+1; D=x.shape[-1]; n=x.shape[0]
    rng=np.random.Generator(np.random.PCG64(cfg_obj['seed']))
    rng.normal(0.0,0.05,size=(D,C)); perm=rng.permutation(n); draws=rng.random(x[perm].shape)
    boundary=float(draws[0,0,0]); assert 0.0 < boundary < 1.0
    cfg_obj['dropout_p']=boundary; Path(cfg).write_text(json.dumps(cfg_obj)+'\n')
    out=tmp_path/'out'; run(cfg,out)
    exp_rows,exp_state=oracle_completed(cfg)
    assert_rows_close(load_trace(out),exp_rows,3e-12)
    assert_states_close(load_state(out),exp_state,3e-12)

def test_dropout_rng_restored_by_resume(tmp_path):
    """High-dropout hidden run proves checkpoint restore includes exact PCG64 state and current permutation."""
    cfg,_,_=hidden_case(tmp_path,n=15,microbatch_size=4,accum_steps=2,dropout_p=.67)
    full=tmp_path/'full'; part=tmp_path/'part'; res=tmp_path/'res'; run(cfg,full); run(cfg,part,stop=5); run(cfg,res,resume=part/'checkpoint.npz')
    assert_rows_close(load_trace(part)+load_trace(res),load_trace(full)); assert_states_close(load_state(res),load_state(full))

def test_example_without_valid_token_fails(tmp_path):
    """An example with no valid token is invalid input and must not produce a completed artifact."""
    cfg,_,_=hidden_case(tmp_path,n=8,t=3,mask_mode='no_valid_example')
    out=tmp_path/'out'; p=run(cfg,out,check=False); assert p.returncode!=0; assert not (out/'final_state.npz').exists()

def test_invalid_nonfinite_input_fails(tmp_path):
    """Non-finite feature data is rejected with nonzero status and no completed artifact."""
    cfg,data,c=hidden_case(tmp_path,n=6)
    with np.load(data,allow_pickle=False) as d: x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()
    for i,bad in enumerate((np.nan,np.inf)):
        xx=x.copy(); xx[0,0,0]=bad; np.savez(data,x=xx,y=y,mask=mask)
        out=tmp_path/f'out_{i}'; p=run(cfg,out,check=False); assert p.returncode!=0; assert not (out/'final_state.npz').exists()

def test_invalid_config_domain_boundaries_fail(tmp_path):
    """Every stated hyperparameter domain is enforced at its acceptance boundary, including warmup<U."""
    bad_values=[
        ('seed',-1), ('epochs',0), ('microbatch_size',0), ('accum_steps',0),
        ('dropout_p',-1e-9), ('dropout_p',1.0),
        ('base_lr',0.0), ('clip_norm',0.0), ('adam_eps',0.0), ('weight_decay',-1e-9),
        ('beta1',-1e-9), ('beta1',1.0), ('beta2',-1e-9), ('beta2',1.0),
        ('warmup_updates',-1),
    ]
    for i,(key,value) in enumerate(bad_values):
        case=tmp_path/f'bad_{i}'; case.mkdir()
        cfg,_,c=hidden_case(case,n=6,t=3,epochs=2,microbatch_size=2,accum_steps=2)
        c[key]=value; Path(cfg).write_text(json.dumps(c)+'\n')
        out=case/'out'; proc=run(cfg,out,check=False)
        assert proc.returncode!=0,(key,value,proc.stdout,proc.stderr)
        assert not (out/'final_state.npz').exists()

    # warmup_updates must be strictly less than U, not <= U.
    case=tmp_path/'bad_warmup_u'; case.mkdir()
    cfg,_,c=hidden_case(case,n=6,t=3,epochs=2,microbatch_size=2,accum_steps=2)
    U=c['epochs']*math.ceil(math.ceil(6/c['microbatch_size'])/c['accum_steps'])
    c['warmup_updates']=U; Path(cfg).write_text(json.dumps(c)+'\n')
    out=case/'out'; proc=run(cfg,out,check=False)
    assert proc.returncode!=0 and not (out/'final_state.npz').exists()


def test_invalid_config_types_and_nonfinite_values_fail(tmp_path):
    """Integer-only fields reject non-integers and finite scalar fields reject NaN/Inf."""
    cases=[('seed',1.5),('seed',True),('epochs',1.5),('epochs',True),('microbatch_size',2.5),('microbatch_size',True),('accum_steps',2.5),('accum_steps',True),('warmup_updates',1.5),('warmup_updates',True),
           ('dropout_p',float('nan')),('dropout_p',True),('base_lr',float('inf')),('base_lr',True),('clip_norm',float('nan')),
           ('beta1',float('inf')),('beta2',float('nan')),('adam_eps',float('inf')),('weight_decay',float('nan'))]
    for i,(key,value) in enumerate(cases):
        case=tmp_path/f'type_{i}'; case.mkdir()
        cfg,_,c=hidden_case(case,n=6,t=3,epochs=2,microbatch_size=2,accum_steps=2)
        c[key]=value; Path(cfg).write_text(json.dumps(c)+'\n')
        proc=run(cfg,case/'out',check=False)
        assert proc.returncode!=0,(key,value,proc.stdout,proc.stderr)



def test_valid_domain_boundary_values_are_accepted(tmp_path):
    """Inclusive valid lower boundaries remain accepted: seed/betas/weight-decay/dropout/warmup zero and unit integer sizes."""
    cfg,_,_=hidden_case(tmp_path,n=5,t=3,d=2,c=3,seed=17,epochs=1,microbatch_size=1,accum_steps=1,
                        dropout_p=0.0,base_lr=.013,warmup_updates=0,clip_norm=.41,
                        beta1=0.0,beta2=0.0,adam_eps=1e-8,weight_decay=0.0)
    c=json.loads(Path(cfg).read_text()); c['seed']=0; Path(cfg).write_text(json.dumps(c)+'\n')
    out=tmp_path/'out'; run(cfg,out)
    exp_rows,exp_state=oracle_completed(cfg)
    assert_rows_close(load_trace(out),exp_rows,3e-12)
    assert_states_close(load_state(out),exp_state,3e-12)

def test_warmup_zero_uses_full_decay_schedule(tmp_path):
    """warmup_updates=0 uses the documented second LR branch on every update, not a constant LR shortcut."""
    cfg,_,_=hidden_case(tmp_path,n=11,t=3,d=3,c=4,epochs=3,microbatch_size=2,accum_steps=2,dropout_p=.19,warmup_updates=0)
    out=tmp_path/'out'; run(cfg,out); rows=load_trace(out); exp_rows,exp_state=oracle_completed(cfg)
    assert len(rows)>2
    assert_rows_close(rows,exp_rows,3e-12); assert_states_close(load_state(out),exp_state,3e-12)
    c=json.loads(Path(cfg).read_text()); U=len(rows)
    expected=[c['base_lr']*(U-u)/U for u in range(U)]
    np.testing.assert_allclose([r['lr'] for r in rows],expected,rtol=1e-14,atol=1e-14)


def test_paused_summary_semantics_before_and_after_update(tmp_path):
    """Paused summaries expose exact global progress and final_loss null/last-trace semantics at both sides of an update."""
    cfg,_,c=hidden_case(tmp_path,n=10,t=3,epochs=2,microbatch_size=2,accum_steps=3,dropout_p=.23)
    early=tmp_path/'early'; run(cfg,early,stop=2)
    ebytes=(early/'summary.json').read_bytes(); assert ebytes.endswith(b'\n')
    es=json.loads(ebytes); assert set(es)==SUMMARY_KEYS
    assert es=={'schema':'resume-train/1','status':'paused','seed':c['seed'],'epochs':c['epochs'],'global_microbatches':2,'optimizer_updates':0,'final_loss':None}
    assert load_trace(early)==[] and (early/'checkpoint.npz').is_file() and not (early/'final_state.npz').exists()

    later=tmp_path/'later'; run(cfg,later,stop=3)
    lbytes=(later/'summary.json').read_bytes(); assert lbytes.endswith(b'\n')
    ls=json.loads(lbytes); rows=load_trace(later); assert len(rows)==1
    assert set(ls)==SUMMARY_KEYS and ls['status']=='paused' and ls['global_microbatches']==3 and ls['optimizer_updates']==1
    assert ls['final_loss']==pytest.approx(rows[-1]['loss'],rel=3e-12,abs=3e-12)
    assert (later/'checkpoint.npz').is_file() and not (later/'final_state.npz').exists()


def test_invalid_shape_and_negative_label_fail(tmp_path):
    """Malformed dataset shape and negative valid labels are rejected rather than trained."""
    cfg,data,c=hidden_case(tmp_path,n=6,t=3)
    with np.load(data) as d: x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()
    y[0,0]=-1; mask[0,0]=1; np.savez(data,x=x,y=y,mask=mask)
    p=run(cfg,tmp_path/'badlabel',check=False); assert p.returncode!=0
    np.savez(data,x=x,y=y[:,0],mask=mask)
    p=run(cfg,tmp_path/'badshape',check=False); assert p.returncode!=0


def test_invalid_stop_boundary_fails(tmp_path):
    """stop-after-microbatch must be a positive global count; both zero and negative targets are rejected."""
    cfg,_,_=hidden_case(tmp_path,n=6)
    for i,stop in enumerate((0,-1)):
        p=run(cfg,tmp_path/f'out_{i}',stop=stop,check=False); assert p.returncode!=0


def test_masked_out_labels_are_ignored_for_class_validation_and_math(tmp_path):
    """Masked-out labels may be arbitrary integers and must not affect class count, validation, loss, or gradients."""
    cfg,data,_=hidden_case(tmp_path,n=9,t=5,d=3,c=4,dropout_p=0.0,microbatch_size=3,accum_steps=2)
    with np.load(data,allow_pickle=False) as d:
        x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()
    assert np.any(mask==0)
    vals=np.where(mask==0)
    y[vals]=np.resize(np.array([-999_999, 999_999],dtype=np.int64),len(vals[0]))
    np.savez(data,x=x,y=y,mask=mask)
    out=tmp_path/'out'; run(cfg,out)
    exp_rows,exp_state=oracle_completed(cfg)
    assert_rows_close(load_trace(out),exp_rows,3e-12)
    assert_states_close(load_state(out),exp_state,3e-12)


def test_dataset_and_config_extension_points_are_accepted(tmp_path):
    """Extra config keys and extra dataset arrays are permitted and cannot change the numerical result."""
    cfg,data,c=hidden_case(tmp_path,n=8,t=3,d=2,c=3,dropout_p=.17)
    with np.load(data,allow_pickle=False) as d:
        x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()
    np.savez(data,x=x.astype(np.float32),y=y,mask=mask.astype(bool),unused=np.arange(5,dtype=np.int64))
    c['unused_config_key']={'note':'ignored'}
    Path(cfg).write_text(json.dumps(c)+'\n')
    out=tmp_path/'out'; run(cfg,out)
    exp_rows,exp_state=oracle_completed(cfg)
    assert_rows_close(load_trace(out),exp_rows,3e-12)
    assert_states_close(load_state(out),exp_state,3e-12)


def test_dataset_dtype_and_shape_contract_boundaries(tmp_path):
    """y must be integer, mask numeric/bool, required arrays must exist, and all tensor dimensions must be positive."""
    base=tmp_path/'base'; base.mkdir(); cfg,data,_=hidden_case(base,n=6,t=3,d=2,c=3)
    with np.load(data,allow_pickle=False) as d:
        x=d['x'].copy(); y=d['y'].copy(); mask=d['mask'].copy()

    cases=[]
    cases.append(dict(x=x.astype(str),y=y,mask=mask))
    cases.append(dict(x=x.astype(np.complex128)*(1+1j),y=y,mask=mask))
    cases.append(dict(x=x,y=y.astype(np.float64),mask=mask))
    cases.append(dict(x=x,y=y,mask=mask.astype(str)))
    cases.append(dict(x=x,y=y,mask=mask[:,:-1]))
    cases.append(dict(x=x[:,:0,:],y=y[:,:0],mask=mask[:,:0]))
    cases.append(dict(x=x[:,:,:0],y=y,mask=mask))
    for i,arrs in enumerate(cases):
        case=tmp_path/f'dtype_shape_{i}'; case.mkdir(); dp=case/'data.npz'; np.savez(dp,**arrs)
        cc=json.loads(Path(cfg).read_text()); cc['data_path']=str(dp); cp=case/'config.json'; cp.write_text(json.dumps(cc)+'\n')
        proc=run(cp,case/'out',check=False); assert proc.returncode!=0,(i,proc.stdout,proc.stderr)
        assert not (case/'out'/'final_state.npz').exists()

    case=tmp_path/'missing_mask'; case.mkdir(); dp=case/'data.npz'; np.savez(dp,x=x,y=y)
    cc=json.loads(Path(cfg).read_text()); cc['data_path']=str(dp); cp=case/'config.json'; cp.write_text(json.dumps(cc)+'\n')
    proc=run(cp,case/'out',check=False); assert proc.returncode!=0


def test_hidden_inputs_remain_byte_identical(tmp_path):
    """Verifier-supplied hidden config and dataset bytes must not be modified by the trainer."""
    cfg,data,_=hidden_case(tmp_path,n=9,t=4,d=3,c=4,dropout_p=.29)
    before={Path(cfg):hashlib.sha256(Path(cfg).read_bytes()).hexdigest(),Path(data):hashlib.sha256(Path(data).read_bytes()).hexdigest()}
    run(cfg,tmp_path/'out')
    after={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    assert after==before

def test_visible_training_is_not_hardcoded(tmp_path):
    """A different hidden dataset/config must train successfully and produce shape-correct state rather than copied visible outputs."""
    cfg,_,c=hidden_case(tmp_path,n=7,t=2,d=5,c=2,microbatch_size=2,accum_steps=2,dropout_p=.1)
    out=tmp_path/'out'; run(cfg,out); st=load_state(out); assert st['W'].shape==(5,2) and st['b'].shape==(2,); assert json.loads((out/'summary.json').read_text())['seed']==c['seed']
