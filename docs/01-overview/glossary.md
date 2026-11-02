<!-- nav:crumb -->
[Docs home](../README.md) › [Overview](README.md) › **Glossary**
<!-- /nav:crumb -->

# Glossary

## Medical terms

| Term | Meaning |
|---|---|
| SEEG | stereo-electroencephalography: depth electrodes record seizures inside the brain |
| Target | a point the electrode must reach; a **target region** is an area where the tip may end anywhere |
| Contact | one recording ring of the electrode; contacts are every 5 mm |
| Entry point | where the robot passes through the skin |
| No-go zone | structure the robot must never touch (with a margin): arteries, veins, ventricles, brainstem, ... |
| Soft zone | allowed but avoided if cheap: eloquent cortex, sulci, deep grey nuclei, minor tracts |
| Eloquent cortex | cortex with a critical function: motor, sensory, visual, auditory, language |
| Tract | bundle of nerve fibres (white matter), found with DTI tractography |
| Prior | a layer from population data or anatomical rules, not measured in this patient |
| Landmark | an easy-to-find point on the face/ears used to align the hologram with the head |

## Methods

| Method | In plain words | Where |
|---|---|---|
| Segmentation (FastSurfer) | a neural network labels every voxel of the T1 with a brain region | [Segmentation](../02-brain-layers/segmentation-and-head.md) |
| Frangi filter | highlights tube-like bright structures (vessels) of several sizes | [Arteries](../02-brain-layers/arteries.md) |
| Tractography | follows the main fibre direction voxel by voxel to trace nerve bundles | [Tracts](../02-brain-layers/white-matter-tracts.md) |
| Registration | finds the movement (and stretch) that puts one scan on top of another | pipeline, headset |
| Euclidean distance transform | every voxel stores how far it is to the nearest voxel of a structure | [Safety maps](../05-path-planning/safety-maps.md) |
| Trilinear interpolation | a value between voxels = weighted mix of the 8 surrounding voxels | safety maps |
| Dijkstra / minimum-cost path | the cheapest way through a grid where every cell has a price, like a satnav | [Planning one path](../05-path-planning/planning-one-path.md) |
| Powell's method | improves a solution by searching along one direction at a time; needs no derivatives | [Shape optimisation](../05-path-planning/shape-optimisation.md) |
| Penalty method with continuation | rules become fines that grow step by step until the rules hold | [Shape optimisation](../05-path-planning/shape-optimisation.md) |
| MILP | choose yes/no for every option so that linear conditions hold and the total cost is minimal, solved exactly | [MILP](../05-path-planning/choosing-the-paths-milp.md) |
| Visual hull | 3D shape = intersection of 2D outlines extruded through the volume | [Target regions](../04-planner-app/target-regions.md) |
| Marching cubes | turns a 3D mask into a triangle surface | 3D view, headset export |
| Kabsch / Horn | best rotation + translation mapping one point set onto another | [Landmark registration](../06-headset-and-unity/landmark-registration.md) |
| ICP | repeatedly match points to the nearest surface point and re-fit | [Landmark registration](../06-headset-and-unity/landmark-registration.md) |

<!-- nav:bar -->
---
← [Coordinates and units](coordinates-and-units.md) | [↑ Overview](README.md) | [Brain layers and patient data](../02-brain-layers/README.md) →
<!-- /nav:bar -->
