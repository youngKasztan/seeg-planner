<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Choosing the paths (MILP)**
<!-- /nav:crumb -->

# Choosing the paths (MILP)

> **In short:** after planning there is a pool of candidate paths - every target alone (with alternatives from other entries) and some group paths. The program must pick a **combination**: every target reached, as few insertions as possible, short and safe paths, and no two chosen paths too close to each other. This is solved exactly with a mixed-integer linear program (MILP).

Code: `Planner._select`, `Planner.conflicts`; solver: `scipy.optimize.milp` (HiGHS).

## Why a MILP

Choosing paths one by one (greedy) fails as soon as paths interact: the cheapest path of one target can block the only good path of another, and a group path is only worth it if its targets are not covered better otherwise. The task is a **set-cover problem with conflicts**: each candidate covers some targets, some pairs of candidates exclude each other. A MILP states exactly that, and the solver returns the guaranteed optimum. With tens of candidates it takes milliseconds.

## Candidates

All feasible paths: per target the best path and up to 2 alternatives with entries at least 15 mm apart ([Final check](final-check.md)), plus every feasible group path ([Several targets](several-targets-on-one-path.md)). Infeasible attempts are not candidates.

## Formulation

Binary variables (0 or 1):
- $`x_c`$ = 1 if candidate path $`c`$ is used;
- $`y_n`$ = 1 if target $`n`$ is declared "not reached".

```math
\min\quad \sum_c (\text{cost}_c + I)\,x_c \;+\; 10^6 \sum_n y_n
```

subject to

```math
\sum_{c\,\ni\,n} x_c + y_n \ge 1 \qquad \forall\ \text{targets } n\qquad\text{(each target covered, or declared not reached)}
```

```math
x_i + x_j \le 1 \qquad \forall\ (i,j) \in \text{conflicts}\qquad\text{(two conflicting paths are never used together)}
```

| Symbol | Value | Meaning |
|---|---|---|
| $`\text{cost}_c`$ | from the optimisation | length + soft zones + bending ([Shape optimisation](shape-optimisation.md)) |
| $`I`$ | `insertion_cost_mm` = 150 | price of one insertion, in mm of path |
| $`10^6`$ | fixed | price of leaving a target unreached: far larger than any path, so the solver first reaches **as many targets as possible**, and only then minimises the cost. The $`y_n`$ also guarantee that a solution always exists |

## Conflicts

`Planner.conflicts` - candidates $`i`$ and $`j`$ conflict when
- they share a target (one path per target is enough), or
- their centre lines come closer than `diameter_mm` + `min_path_distance_mm` = 2 + 2 = **4 mm** at any point (k-d tree), i.e. the robot surfaces would be closer than 2 mm, or
- their skin entries are closer than `min_entry_distance_mm` = **10 mm**.

## Worked example

Three targets A, B, C. Candidates:

| Candidate | Targets | Path cost | + insertion (150) |
|---|---|---|---|
| $`P_A`$ | A | 70 | 220 |
| $`P_B`$ | B | 80 | 230 |
| $`P_C`$ | C | 60 | 210 |
| $`P_C'`$ (alternative entry) | C | 72 | 222 |
| $`P_{AB}`$ | A, B | 110 | 260 |

Conflict: $`P_{AB}`$ passes 3 mm from $`P_C`$ (< 4 mm).

| Combination | Allowed? | Total |
|---|---|---|
| $`P_A + P_B + P_C`$ | yes | 660 |
| $`P_{AB} + P_C`$ | **no** (conflict) | 470 |
| $`P_{AB} + P_C'`$ | yes | **482** <- optimum |

Greedy (cheapest path per target) gives 660 with three insertions. The MILP finds two insertions for 482, using the alternative entry for C - this is why alternatives are kept.

## After the MILP

Chosen paths = $`x_c > 0.5`$. For each target that is not covered, the log gives the reason: `its paths come too close to another chosen path` (it had a feasible path, lost to a collision), `no path satisfies all constraints`, or the message of the target check.

<!-- nav:bar -->
---
← [Several targets on one path](several-targets-on-one-path.md) | [↑ Path planning](README.md) | [Electrode contacts](electrode-contacts.md) →
<!-- /nav:bar -->
