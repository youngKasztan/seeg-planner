<!-- nav:crumb -->
[Docs home](../README.md) › [Overview](README.md) › **Path planning in plain words**
<!-- /nav:crumb -->

# Path planning in plain words

> This page explains the idea of the planner without formulas. The full description is in [Path planning](../05-path-planning/README.md).

## The problem

The surgeon marks places in the brain (points, or areas drawn on the slices) that the electrode must reach. The robot enters through skin and skull and must reach each place **without touching** anything dangerous - arteries, veins, ventricles, the brainstem, important nerve tracts - always keeping a safety margin. It can only take shapes it is physically able to make, and it should prefer gentle, short paths that also stay away from areas that are allowed but better avoided (e.g. the motor or language cortex).

## What the robot can do

The robot is not a straight needle. It is pushed in straight; then two pre-curved tubes come out of it, one after the other. Each tube can be rotated, so each bends in its own direction:

```
skin ──── straight part ────╮ arc 1 (wide bend) ╮ arc 2 (tighter bend) ● tip on the target
```

So every path is **a straight line + a circular arc + another circular arc**. Finding a path means finding the few numbers that describe this shape: the lengths, how strongly and in which direction each arc bends. Details: [Robot model](../03-robot-and-config/robot-model.md).

## The idea in five steps

1. **A map of danger.** For every point of the head the program computes how far it is from the nearest dangerous structure, minus the safety margin. Positive = safe, negative = too close. Allowed-but-unwanted areas get a second map: a "price" per millimetre of path. [Safety maps](../05-path-planning/safety-maps.md)
2. **A rough route first.** Like a satnav on a coarse 2 mm grid, Dijkstra's algorithm finds the cheapest way from the skin to the target, avoiding forbidden cells and paying more near danger. The robot cannot follow this zig-zag route exactly, but it shows *where* a good path goes through the maze. [Route grid](../05-path-planning/route-grid-and-entry-points.md), [One path](../05-path-planning/planning-one-path.md)
3. **Fit the real robot shape.** The shape numbers are adjusted so that the robot lies along the rough route. The shape is built **backwards from the target**, so the tip is always exactly on it.
4. **Polish the shape.** The shape is improved: shorter, gentler, further from danger. Rules that must never be broken are first handled as fines that grow step by step until no rule is broken. At the end a strict check decides; a shape that breaks any rule is thrown away. [Optimisation](../05-path-planning/shape-optimisation.md), [Final check](../05-path-planning/final-check.md)
5. **Choose the best combination.** Every target gets its own path, and groups of nearby targets are tried on one path. A small integer program (MILP) then picks the cheapest set of paths that reaches all targets, where every extra insertion is expensive and paths that come too close to each other cannot be used together. [Several targets](../05-path-planning/several-targets-on-one-path.md), [MILP](../05-path-planning/choosing-the-paths-milp.md)

## Why it is built like this

| Choice | Why |
|---|---|
| Danger maps computed once | the optimiser checks thousands of shapes; looking up a stored number is fast |
| Rough route before the robot shape | an optimiser only improves what it starts from; a start on the wrong side of an artery never gets around it. Dijkstra explores the whole brain and finds the cheapest route on its grid |
| Shape built from the target backwards | the tip is on the target by construction; the optimiser never has to "aim" |
| Fines during the search, strict check at the end | a search that rejects every slightly wrong shape gets stuck; fines let it pass through nearly-good shapes. Safety is decided only by the final check |
| Several starting routes | the optimiser is local; trying several skin entries lowers the risk of a poor result |
| MILP at the end | choosing a combination of paths with collisions between them is combinatorial; the MILP finds the true optimum, not a greedy guess |

<!-- nav:bar -->
---
← [What the system does](what-the-system-does.md) | [↑ Overview](README.md) | [Coordinates and units](coordinates-and-units.md) →
<!-- /nav:bar -->
