<!-- nav:crumb -->
[Docs home](../README.md) › [Project and repository](README.md) › **Limitations and roadmap**
<!-- /nav:crumb -->

# Limitations and roadmap

## Limitations

| Area | Limitation |
|---|---|
| robot | arc radii and lengths are assumptions until the real robot is built |
| contacts | contacts on earlier targets of a multi-target path are checked, not optimised |
| eloquent cortex | atlas-based (no fMRI), soft zone only; language assumed left-dominant |
| veins, sagittal sinus | priors (no venography in the test data) |
| skull | T1 estimate; bone thickness and drilling angle need CT |
| entry angle | uses the smoothed normal of the 2 mm skin grid, not the exact skull surface |
| optimiser | local (Powell); several starts reduce, but do not exclude, missed better paths |
| groups | combinatorial and time-limited; rarely feasible on IXI057 with the current limits |
| tracts | 16-direction DTI, tensor model (no crossing fibres); not compared with experts |
| registration | touched landmarks only, no tool-tip calibration, no ICP on the headset yet; model is IXI057, not the wearer |
| head tracking | blocked on the current Quest 3 (runtime) |
| validation | veins from contrast T1 and CT layers tested on phantoms only |
| code | `Planner._free_dirs` is unused |

## Next steps

- confirm the arc parameters (radii, which arc bends more) with the robot design;
- reward paths with several contacts inside a target region; force contacts onto intermediate targets;
- decide: eloquent cortex as no-go except the gyrus of the target;
- test QR tracking on an unmanaged headset, or ArUco via the Passthrough Camera API; move it from the test copy into the main Unity project;
- tool-tip calibration of the controller, ICP on the scalp, an MRI of the person wearing the headset instead of IXI057;
- "Load plan" in the app;
- a patient with venography / CT (e.g. Brainstorm epileptogenicity dataset);
- answers from the neurosurgeon questionnaire.

<!-- nav:bar -->
---
← [Repository structure](repository-structure.md) | [↑ Project and repository](README.md) | [Data sources and safety](data-sources.md) →
<!-- /nav:bar -->
