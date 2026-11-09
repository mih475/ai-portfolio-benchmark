# Playbook archive — frozen, proven reference

This folder holds **frozen snapshots** of playbooks that have been validated and
are worth never losing. Files here are reference copies — nothing in the
experiment loads them at runtime, so they can't be altered by a run or a tweak.

## `claude_aggressive_PROVEN_v1.md`

An exact copy of `v2/data/playbooks/claude_aggressive.md` as of the backtests that
proved its worth. **This is the validated baseline.** If the live
`claude_aggressive.md` is ever changed and we want to get back to the proven
version, restore from this file (or the git tag below).

### Why it's worth keeping — what it proved

- **Bear market (2022), 3 runs:** ended ≈flat (−0.0% / −4.3% / −2.4%) while SPY
  fell −21.8%; beat SPY in **all 12 quarter-runs**; single-digit drawdowns vs
  SPY's 13–20%; **86% pooled beat-rate that did not decay** — by going to cash.
- **Bull market (2024–25), 3 runs:** modest, noisy edge (pooled **60% beat-rate /
  +4.4% margin**; the flashy single-run +84% did not reproduce).
- **Character:** a defensive, drawdown-averse, cash-timing agent — its value is
  capital preservation in down markets, not raw upside. It is the only one of
  nine agents across three model families to stand out. Full detail in
  `FINDINGS.md`.
- **Not transferable by prompt:** handing this exact playbook to `gpt-6-luna`
  (`chatgpt_aggressive`) did **not** reproduce the defense — it lost −24% in 2022
  (worse than SPY). The edge is in how `claude-haiku-5-5` executes the playbook,
  not the text alone.

### Restore points

Primary (always works — this frozen copy is committed on `main`):
```
cp v2/data/playbooks/archive/claude_aggressive_PROVEN_v1.md \
   v2/data/playbooks/claude_aggressive.md
```

Optional named tag `proven-aggressive-v1` marks the exact commit with the
validated playbook + supporting code. It could not be pushed from the build
environment (proxy blocks tag refs); to publish it from a normal clone:
```
git tag -a proven-aggressive-v1 8044be2 -m "Validated claude_aggressive baseline"
git push origin proven-aggressive-v1
```
Then restore with: `git checkout proven-aggressive-v1 -- v2/data/playbooks/claude_aggressive.md`

**Do not edit the files in this archive.** New ideas go into new variant playbooks
(e.g. `claude_robust.md`, `claude_return.md`), never into the baseline or these
snapshots.
