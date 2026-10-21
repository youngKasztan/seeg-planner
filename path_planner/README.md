# Continuum robot path planner (desktop app)

Pick targets on the MRI slices, compute safe curved paths for a continuum robot, export them to the headset.
The headset only displays the result (brain + paths); all planning happens here.

![app](../docs/path_planner_app.png)

## Use
1. **Open patient folder** - the output folder of `pipeline/run_pipeline.py` (needs `orig.nii.gz`,
   `aparc.DKTatlas+aseg.deep.nii.gz`, `head.nii.gz`, `mask.nii.gz`, the masks named in `robot.toml`, and
   `headset/headset_manifest.json`). Loading takes ~30 s (safety maps are computed).
2. **Targets**: scroll through axial / coronal / sagittal slices (mouse wheel, Shift = 5 slices),
   **left click** adds a target on the current slice, **right click** moves the cursor. Targets can be on
   different slices. Double click a target to rename it. A target that is itself inside a no-go zone is shown
   in red; *Snap to safe point* moves it to the closest safe point (max 5 mm).
   **Layers** (right panel, tick to show on the slices and in 3D; the planner always uses every zone,
   ticked or not). One tick per group shows or hides the whole group; expand a group to tick single layers.
   All no-go zones are shown at start (except *outside_brain*, which would cover the whole head).
   - *No-go zones* and *Soft zones* = exactly the zones the planner uses (from `robot.toml`), with their margins / weights
   - *Anatomy, Head* = display only (they do not change the plan): grey / white matter, CSF, hippocampus,
     amygdala, thalamus, basal ganglia, skull estimate, scalp. Structures that are already a zone
     (ventricles, vessels, eloquent cortex, tracts ...) are shown from their zone row, not twice.
     [PRIOR] / [ESTIMATE] / [atlas function] mark layers that are not measured in this patient
   **Target regions** (doctors usually mark an area, not a point): press **Draw outline** (or *New region*),
   hold the left mouse button and draw around the area on a slice of one view, then on a slice of a second view
   (e.g. axial, then coronal; the other views jump to the region after the first outline). The region is where
   the outlines overlap (each outline is extended through the volume along its view); with one outline only it
   is a 5 mm slab. *Region only inside the brain* clips it to the brain. Drawing again in a view replaces that
   outline. Regions are saved automatically to `regions.json` (outlines in RAS mm); *Save targets* also writes
   `regions/<name>.nii.gz`. When planning, the robot tip may end **anywhere inside the region**: the planner takes
   safe points at least 1.5 mm inside its edge, ranks them by the route cost from the skin (one Dijkstra from all
   allowed entries), plans the 3 best in full and keeps the cheapest; then the region is planned like a point
   target (also together with other targets on one path). The path list shows how many electrode contacts lie in
   the region. The region is exported to the headset as layer `region_<name>` (group *Target regions*).
3. **Plan paths** - for every target, and for groups of 2-3 nearby targets, the planner looks for a path;
   it then decides itself how many insertions are needed (one path through several targets when that is safe).
   Every target alone takes ~10-20 s. Groups are tried after that, most promising first, until
   `time_limit_s` (robot.toml, default 120 s); groups that cannot be shorter than separate paths are skipped.
   **Stop** ends the planning at any time; if the single paths are already done they are kept.
4. **Export to headset** - writes into `headset/` (about 1 min):
   - `plan.json` (targets, path points in mm and in headset metres, checks) and `paths.glb` (robot tubes + targets)
   - `patient_scene.glb` / `patient_scene_lite.glb` and the `layers` of `headset_manifest.json`: the brain model with
     **the same layers and groups as this app** (No-go zones, Soft zones, Anatomy, Head; outside_brain left out).
     The original model of `tools/export_headset.py` is kept once as `*_pipeline.glb` / `headset_manifest_pipeline.json`;
     landmarks and the coordinate system in the manifest are not changed.
   The Unity app (`PatientLoader` + `DesktopViewer`) loads all of it on Play: same groups, one tick per group.
   Copy the headset folder to the glasses as before.

## Robot constraints and no-go zones: `robot.toml`
All limits are in `robot.toml` (next to the exe after building): robot diameter, minimum bend radius,
maximum length, straight entry length, entry angle, total turning; no-go zones (hard, with safety margins)
and soft zones (preferred distance). Edit, save, press **Reload robot.toml**. No code changes needed.

| No-go zone (hard) | Source | Margin |
|---|---|---|
| arteries | TOF-MRA, automatic segmentation | 2 mm |
| ventricles | T1 segmentation | 1.5 mm (not checked right at a target) |
| choroid plexus | T1 segmentation | 1 mm |
| midline (falx, interhemispheric fissure, corpus callosum midline) | computed from the segmentation | 1 mm - a path never crosses to the other hemisphere |
| hypothalamus (ventral diencephalon), optic chiasm | T1 segmentation | 2 mm |
| brainstem, cerebellum | T1 segmentation | 3 mm, 1 mm |
| superior sagittal sinus | PRIOR from anatomical rules (no venography) | 3 mm |
| outside the brain (after the straight entry) | brain mask | 1 mm |

Soft zones (allowed, the planner keeps away): veins (VENAT atlas PRIOR), deep grey nuclei (may be targets),
sulci, eloquent cortex (DKT atlas), corticospinal tract, optic radiation, other tracts (DTI).

## Electrode contacts
The robot carries an SEEG electrode whose recording contacts are not continuous: there is one contact every
`contact_spacing_mm` (default 5 mm, `[electrode]` in `robot.toml`). Contact 1 sits at the tip, on the last target
of the path; the others follow back along the curved path every 5 mm of arc length (none in the straight entry
through skin and bone). `electrode.py` computes them; the app shows them with **Show electrode contacts**:
squares = contacts on the current slice, faint dots = contacts on other slices, green ring = a contact lying on a
target (contact centre at most `on_target_mm` = 1.5 mm from it). The path list says which contact records each
target and how far it is, e.g. `hip: #1 0.0 mm | amy: #4 0.8 mm`; a target that falls between two contacts is shown
in red. The export writes the contacts into `plan.json` (per path: number, depth from the tip, position, on target)
and as bands into `paths.glb` (`path_<n>_contacts` silver, `path_<n>_contacts_on_target` green), so the headset
shows them too.

## How a path is found
1. Coarse route on a 2 mm grid (minimum-cost path, `skimage.graph.MCP`): impassable in no-go zones,
   expensive near them and in soft zones.
2. The robot path = straight entry (through skin and bone) + cubic spline through the targets.
   The spline is optimised (`scipy` L-BFGS) for: no-go clearance (hard), bend radius >= minimum (hard),
   entry angle, total turning and length limits (hard), then short + sweeping + far from soft zones.
   Several starting guesses (coarse routes from different entries, straight lines) are tried.
3. Every result is checked against all hard limits; only paths that pass are used.
4. An integer program (`scipy.milp`) picks the set of paths that covers all targets with the lowest
   `path cost + insertion_cost_mm` per insertion. Paths used together must not collide: their robot bodies
   keep `min_path_distance_mm` apart and their skin entries `min_entry_distance_mm` apart. For every target
   up to 3 feasible paths from different entries are kept, so a clash is solved by taking another entry;
   a target that still cannot get a non-colliding path is reported in the log.

## Build the Windows exe
Double click `build_exe.bat` (Python 3.11 must be installed). Result: `dist\ContinuumPathPlanner\ContinuumPathPlanner.exe`.
Without building: `run_app.bat` (or `python app.py`). Self-test without a window: `python app.py --selftest <patient folder>`.

Note: Windows Smart App Control may block an unsigned exe. If it does, use `run_app.bat`.

The 3D view uses pyqtgraph + PyOpenGL (pure Python, drawn by the system OpenGL driver). The earlier VTK /
pyvista view was blocked by Smart App Control (unsigned `vtk*.dll`). 3D mouse: left drag = rotate,
wheel = zoom, middle drag = move; buttons Front / Left / Right / Top reset the view.

## Test
`python tests/test_path_planner.py` - synthetic head: artery above a target, two targets on one line (one path),
target inside an artery (reported), Stop during planning, time limit, two crossing paths (alternative entry used).

Research prototype - not for clinical use.
