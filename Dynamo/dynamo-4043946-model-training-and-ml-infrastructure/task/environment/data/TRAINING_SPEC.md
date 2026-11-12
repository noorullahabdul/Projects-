# Training loop contract

This file is normative. `/app/trainer.py` must implement every rule below for any valid input that follows this contract.

## CLI

```
python3 /app/trainer.py --config CONFIG --out OUT [--resume CHECKPOINT] [--stop-after-microbatch N]
```

`CONFIG` is JSON. `OUT` is created if needed. `--stop-after-microbatch N` is optional and `N` is a positive **global** microbatch count measured from the beginning of the complete training job, not from the current process. When the trainer reaches exactly global microbatch `N`, it must persist a resumable checkpoint at `OUT/checkpoint.npz`, write `OUT/summary.json` with `status="paused"`, and exit successfully. It must not perform any extra microbatch or optimizer update after that boundary. If the Nth microbatch itself completes an accumulation group, that optimizer update is performed before the checkpoint is written. A resumed invocation has no implicit stop unless `--stop-after-microbatch` is supplied again.

`--resume CHECKPOINT` continues the job described by the current config and dataset. Resume equivalence is defined when the resumed invocation uses the same effective config values and dataset bytes that created the checkpoint; behavior for deliberately mismatched checkpoint/config/data combinations is outside this task contract. The checkpoint must contain enough state to continue from the exact next microbatch without replay, skip, or loss of an unfinished accumulation group. A checkpoint created in the middle of a group therefore has to preserve pending accumulated gradients and the pending valid-token count in addition to model/optimizer/training-position/RNG state. The checkpoint's internal representation is otherwise implementation-defined.

## Input

The config contains exactly these required settings: `data_path`, `seed`, `epochs`, `microbatch_size`, `accum_steps`, `dropout_p`, `base_lr`, `warmup_updates`, `clip_norm`, `beta1`, `beta2`, `adam_eps`, and `weight_decay`. Extra JSON keys may be ignored. Here, an integer means a JSON integer (not a boolean), and a numeric scalar means a JSON number (not a boolean). Their valid domains are: `seed` is an integer accepted by NumPy PCG64; `epochs`, `microbatch_size`, and `accum_steps` are positive integers; `dropout_p` is finite with `0 <= dropout_p < 1`; `base_lr`, `clip_norm`, and `adam_eps` are finite and strictly positive; `beta1` and `beta2` are finite with `0 <= beta < 1`; `weight_decay` is finite and nonnegative; and `warmup_updates` is a nonnegative integer strictly smaller than the total optimizer-update count `U` defined below. Invalid values must fail with a nonzero exit status instead of emitting a completed result.

The `.npz` dataset must contain arrays named `x`, `y`, and `mask`; extra arrays may be ignored. The three required arrays are:

- `x`: finite real numeric array `[examples, tokens, features]`, interpreted as `float64`;
- `y`: integer class IDs `[examples, tokens]`;
- `mask`: numeric or boolean `[examples, tokens]`; a token is valid iff its mask value is nonzero.

Every example must contain at least one valid token. Class count is `max(y[mask != 0]) + 1`. Only valid-token labels, meaning `y[mask != 0]`, participate in the class-count calculation and label-range validation. Valid-token labels outside `[0, classes)` must fail. Labels at masked-out positions (`mask == 0`) are ignored for class-count/range validation and for loss/gradient computation; they may contain any integer value. The `examples`, `tokens`, and `features` dimensions must all be positive. Invalid shapes, a non-integer `y`, a non-numeric/non-boolean `mask`, non-finite `x`, an example with no valid token, or config values outside their stated domains must fail with a nonzero exit status instead of emitting a completed result. Extra config keys and extra dataset arrays may be ignored.

## Model and initialization

The model is a token-wise linear softmax classifier: `logits = x @ W + b` with `W[features, classes]` and `b[classes]`.

Use one NumPy `Generator(PCG64(seed))` for all stochastic operations. Initialize `W` from `Normal(0, 0.05)` using that generator and initialize `b` to exact zeros. Initialize Adam first and second moments for both arrays to zeros. RNG consumption order is therefore observable and must be preserved on resume.

## Epochs, shuffling, microbatches, dropout

At the beginning of each epoch obtain `perm = rng.permutation(examples)`. Iterate that permutation in contiguous microbatches of at most `microbatch_size`; never drop the final short microbatch.

Immediately before the forward pass of each microbatch, draw a random array with the same shape as that microbatch's `x` using the same generator. Apply inverted dropout elementwise to **all** feature elements: when `dropout_p > 0`, `x_drop = x * (rand >= dropout_p) / (1-dropout_p)`; when it is zero, use `x` and consume no dropout random numbers. Masking still decides which token losses/gradients count.

A resumed job must continue with the already-created permutation of the current epoch and with the exact RNG state after the previous microbatch. Do not regenerate the current epoch permutation on resume.

## Loss and gradient accumulation

For each valid token, use ordinary softmax cross-entropy. Compute numerically stable softmax by subtracting the per-token maximum logit. Each microbatch contributes **sums**, not means: sum cross-entropy over valid tokens and sum the corresponding gradients of `W` and `b` over valid tokens.

Accumulate those gradient sums, loss sums, and valid-token counts across consecutive microbatches. An optimizer update happens after `accum_steps` microbatches or at the end of the epoch, whichever occurs first. Thus every epoch flushes its final partial accumulation group.

At an optimizer update, divide the accumulated gradient sums and accumulated loss sum by the **total valid-token count of that accumulation group**. Do not average per-microbatch means, and do not divide a partial group by `accum_steps`. ## Gradient clipping

Let `gW` and `gb` be the normalized accumulated gradients. Compute the pre-clip global L2 norm as `sqrt(sum(gW^2) + sum(gb^2))`. If and only if this value is strictly greater than `clip_norm`, multiply both gradients by `clip_norm / norm`. Equality does not clip. Clipping occurs once per optimizer update after normalization and before Adam moment updates. `grad_norm_postclip` is the global norm after this operation. The trace field `clipped` is a JSON boolean that is `true` exactly when this strict comparison fires; therefore it is `false` when `grad_norm_preclip == clip_norm`.

## Learning-rate schedule and AdamW

Let `u` be the zero-based optimizer-update index before the current update and let `U` be the total number of optimizer updates that the complete run would perform, counting every nonempty full or partial accumulation group in every epoch. Valid configs have `0 <= warmup_updates < U`.

The learning-rate factor is:

- if `u < warmup_updates`: `(u + 1) / warmup_updates`;
- otherwise: `(U - u) / (U - warmup_updates)`.

When `warmup_updates == 0`, always use the second branch. `lr = base_lr * factor`. The schedule advances once per optimizer update, never per microbatch.

For update number `t = u + 1`, use Adam moments
`m = beta1*m + (1-beta1)*g` and `v = beta2*v + (1-beta2)*g*g`, bias-correct both moments with powers `beta1**t` and `beta2**t`, then update each parameter with decoupled weight decay:
`param = param - lr * (m_hat / (sqrt(v_hat)+adam_eps) + weight_decay*param)`.
Apply this rule to both `W` and `b` using their own moments. The weight-decay term uses the parameter value before the current update.

## Outputs

All JSON is UTF-8, uses JSON numbers for finite floats, and ends with a newline. JSON key ordering is not significant.

### `OUT/train_trace.jsonl`

One JSON object per optimizer update, in update order, with exactly these keys:

`update`, `epoch`, `group_microbatches`, `global_microbatch`, `valid_tokens`, `lr`, `loss`, `grad_norm_preclip`, `grad_norm_postclip`, `clipped`.

`update` and `epoch` are 1-based. `global_microbatch` is the number of the final microbatch included in the update. `loss` is the group's valid-token-normalized loss before the parameter update. No trace row is written for an empty-valid-token group.

### `OUT/final_state.npz`

On completed training only, contain exactly these arrays: `W`, `b`, `m_W`, `v_W`, `m_b`, `v_b`. Arrays must be finite. Do not write this file for a paused run.

### `OUT/summary.json`

For a completed run, contain exactly:

`{"schema":"resume-train/1","status":"completed","seed":...,"epochs":...,"global_microbatches":...,"optimizer_updates":...,"final_loss":...}`

For a paused run, use the same keys with `status="paused"`; `optimizer_updates` is the number already performed and `final_loss` is the most recent trace loss, or `null` if no update has yet occurred. `global_microbatches` is the count already processed.

## Determinism and resume equivalence

For identical input bytes and config, two fresh runs must match numerically. More importantly, if a completed run is compared with a run paused at any legal microbatch and then resumed, the concatenated pre-pause and post-resume trace must match the uninterrupted trace row-for-row (floating values within ordinary IEEE-754 roundoff), and all six arrays in `final_state.npz` must match within `1e-12` absolute and relative tolerance.

The trainer must not modify the dataset, config, or this specification file, including when invoked on verifier-supplied hidden config/data paths.
