# Phase 4: Controlled Experiment & Academic Rigor

This plan refines the final experiment to meet "paper-level" standards for reproducibility and statistical limits.

## Proposed Changes

### 1. Parameter Scale-up

- **N = 30**: Adjusted to standard "Golden Batch" target (30 repeats per condition).
- **Rounds = 15**: To capture long-term convergence trajectories.
- **Seeds = 30**: Targeting N=30 runs per condition (Total 150 runs including C0).
- **Control Group (C0)**: Mandatory inclusion (N=10 minimum) to establish baseline drift.
- **Stopping Criterion**: Monitor 95% Confidence Interval (CI) width of TTC. If CI is wide, extend runs.

### 2. Initialization Strategy & Controls

- **Configurable Initial Stance**: Add `--enforce-initial` flag to `run_batch.py`.
- **Manipulation Check**: Round 1 prompts must explicitly echo: "Your initial position is [STANCE]" to verify 15:15 split is perceived.
- **Metric Definitions**:
  - **Tau ($\tau$)**: Defined as **Entropy < 0.469** (90:10 split) for 2 consecutive rounds. absolute threshold is more robust than relative.

### 3. Automated Reporting

- **Visualization Upgrade (Publication Quality)**:
  - **Stacked Bar Charts**: Replace pie charts to allow accurate comparison of magnitude.
  - **Swarm Plots**: Overlay individual run data points on TTC bar charts to show variance.
  - **Survival Analysis**: Add censorship markers (+) to KM curves.
  - **Captions**: Auto-generate academic captions stating (N, $\tau$, Conditions).

## Verification Plan

- Run a 3-round test with N=50 to check for memory overflows.
- Verify that `merged_report.txt` correctly aggregates N=50 data.
