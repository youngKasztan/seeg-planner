<!-- nav:crumb -->
[Docs home](../README.md) › [Path planning](README.md) › **Several targets on one path**
<!-- /nav:crumb -->

# Several targets on one path

> **In short:** one insertion that records several targets is better for the patient than several insertions. The planner lists which targets could share a path (before planning), plans every target alone, then tries the groups - with special exact starting shapes - until the time limit. The [MILP](choosing-the-paths-milp.md) then decides whether a group path is worth using.

## 1. List of groups (made before the single paths)

`Planner._candidate_groups`: for $`k`$ = 2 ... `max_targets_per_path` (3), every combination of $`k`$ targets and every order (permutation) of it. An order is kept when

- consecutive targets are at most `group_max_distance_mm` = 60 mm apart, and
- each step $`a \to b`$ passes the order test below.

Each kept order gets its **rough route cost** (Dijkstra skin -> first target + target-to-target legs); orders are sorted by it. Groups are sorted by size (pairs first), then by their best rough cost. This step runs the Dijkstra of every target, which is cached and reused by the single paths.

## 2. Order test: can the robot pass a and then reach b?

`Planner.order_possible(a, b)`. A curve leaving $`a`$ with tangent $`t`$ and curvature at most $`1/R`$ reaches a point at distance $`d`$ only if the angle between $`t`$ and the chord $`a \to b`$ is at most $`\arcsin(d/2R)`$ (the circular arc is the extreme case). With $`R`$ = the tightest radius of the robot (30 mm):

```math
\theta_{\max} = \arcsin\!\big(\min(1,\ d/2R)\big) + 10°
```

The tangent at $`a`$ must be a direction the robot can arrive from: 6000 random unit directions are tested and kept if the 8 mm chord towards $`a`$ (12 samples from 3.5 to 8 mm) has $`C_{\text{strict}} > -1`$ and $`C_{\text{ign}} > -1`$ (1 mm slack for the real curve). The order is possible if some arrival direction is within $`\theta_{\max}`$ of the chord. The +10° covers the chord approximation and the sampling.

> This is a **necessary** condition: it removes impossible orders cheaply, it does not prove that an order works.

## 3. Exact arc starting shapes

`_arc_inits`: an exact shape through the targets is computed geometrically and optimised directly. $`P`$ = second-to-last target, $`T`$ = last target.

- **Direction through $`P`$:** for 3 targets, the direction from the first to the second target; for 2 targets, the directions of straight-entry lines through $`P`$ whose angle to $`P \to T`$ is at most $`\arcsin(\lVert T-P\rVert\,\kappa_{2,\max}/2) + 2°`$ (6 tried).
- **Arc start** $`S = P + t\,d`$, $`t \in \{0, 4, 8, 12\}`$ mm. Chord $`c = T - S`$, $`L = \lVert c\rVert`$, $`\theta = \angle(d, c)`$. The circular arc tangent to $`d`$ at $`S`$ that passes through $`T`$:

```math
R = \frac{L}{2\sin\theta},\qquad \kappa = \frac{1}{R},\qquad s = 2\theta R,\qquad v_{\text{tip}} = \cos(2\theta)\,d + \sin(2\theta)\,n_c
```

  ($`n_c`$ = unit normal of $`d`$ in the plane of $`d`$ and $`c`$).
- Rejected if $`\kappa > \kappa_{2,\max}`$ or $`s > 70`$ mm. The arc is split: $`L_2 = \min(s, 35)`$, $`L_1 = s - L_2`$ (then also $`\kappa \le \kappa_{1,\max}`$). Both planes are set so that the arcs bend towards the circle centre $`S + n_c/\kappa`$.
- The 3 best shapes go straight to the [penalty continuation](shape-optimisation.md).

## 4. Second-to-last target at the arc junction

`_optimise_via`: the robot may already be curved when it passes $`P`$. Here $`P`$ lies exactly where arc 1 meets arc 2, and arc 2 is the circular arc from $`T`$ (tip direction $`v`$) through $`P`$:

```math
w = P - T,\quad c = \lVert w\rVert,\quad \theta = \arccos\!\Big(\frac{v\cdot w}{c}\Big),\quad R_2 = \frac{c}{2\sin\theta},\quad L_2 = 2\theta R_2
```

The remaining numbers $`[a, b, L_1, \kappa_1, \varphi_1]`$ are fitted to the rough route skin -> $`P`$ (2 entries) with an extra term $`100\,\text{over}^2`$, then optimised with the full objective (including $`200\,V_{\text{over}}`$, which penalises an arc 2 beyond the robot's limits).

## 5. Planning the groups

After all single targets, for each group (pairs first, most promising first):

1. a triple is only tried if all its pairs gave feasible paths;
2. if `time_limit_s` (240 s) is reached, the group is skipped;
3. **pruning** (`_cannot_win`): skipped if it provably cannot beat separate paths;
4. otherwise its orders are planned (cheapest rough route first) with [Planning one path](planning-one-path.md) in group mode - exact arc shapes, junction shapes, then the general starts - stopping at the first feasible path; other orders of the same targets are not tried.

**Pruning:** any path through the group is at least as long as

```math
\text{LB} = \min_{\text{orders}}\Big(\min_{e}\lVert e - p_{\text{first}}\rVert + \sum_i \lVert p_{i+1} - p_i\rVert\Big)
```

(nearest allowed entry to the first target, plus target-to-target distances; path cost >= length >= LB). The best known cover of the same targets with paths already found:

```math
B = \min\Big(\sum_{n} (\text{cost}_n + I),\ \ \text{cost}_{\text{pair}} + I + \sum_{n \notin \text{pair}} (\text{cost}_n + I)\Big),\qquad I = \texttt{insertion\_cost\_mm}
```

The group is skipped if $`\text{LB} + I \ge B`$. The log reports how many groups were pruned and how many were skipped by the time limit.

<!-- nav:bar -->
---
← [Final check and best result](final-check.md) | [↑ Path planning](README.md) | [Choosing the paths (MILP)](choosing-the-paths-milp.md) →
<!-- /nav:bar -->
