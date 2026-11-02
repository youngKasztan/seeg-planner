"""
docs_nav.py - navigation for docs/: breadcrumbs, previous / up / next bar, page lists on the home and category pages.

Usage:  python tools/docs_nav.py
The reading order, titles and descriptions are defined in PAGES below. Generated parts sit between
<!-- nav:... --> comments and are replaced on every run; everything else in a page is left as written.
"""
import os, re

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")

# (folder, category title, [(file, title, one-line description), ...])
PAGES = [
    ("01-overview", "Overview", [
        ("what-the-system-does.md", "What the system does", "goal, the three parts, data flow, a typical session"),
        ("planning-in-plain-words.md", "Path planning in plain words", "the idea of the planner without formulas, and why it is built this way"),
        ("coordinates-and-units.md", "Coordinates and units", "scanner RAS, voxel grid, anatomical head frame, headset scene"),
        ("glossary.md", "Glossary", "medical terms and methods in plain words"),
    ]),
    ("02-brain-layers", "Brain layers and patient data", [
        ("running-the-pipeline.md", "Running the pipeline", "one command, required exams, steps, patient folder"),
        ("segmentation-and-head.md", "Segmentation and head mask", "FastSurfer labels, head mask, anatomy layers"),
        ("arteries.md", "Arteries from TOF-MRA", "registration, Frangi filter, thresholds, validation (Dice 0.78)"),
        ("white-matter-tracts.md", "White-matter tracts from DTI", "tractography, automatic bvec check, the 9 tracts"),
        ("veins-sinuses-and-ct.md", "Veins, sinuses and CT", "contrast-T1 subtraction, CT bone and contacts"),
        ("sulci-skull-and-priors.md", "Sulci, skull and priors", "sulci, skull estimate, sagittal sinus rule, VENAT venous atlas"),
        ("eloquent-cortex.md", "Eloquent cortex", "motor, sensory, visual, auditory and language areas from the atlas"),
        ("layer-catalogue.md", "Layer catalogue", "every layer: source, origin, role in the planner, margin / weight"),
        ("headset-package-and-landmarks.md", "Headset package and landmarks", "3D scene, manifest, phantom, automatic face and ear landmarks"),
    ]),
    ("03-robot-and-config", "Robot and configuration", [
        ("robot-model.md", "Robot model", "straight part + 2 arcs, arc formula, shape built backwards from the target"),
        ("configuration-file.md", "The configuration file robot.toml", "how it is read and reloaded, the full current file"),
        ("config-robot-and-electrode.md", "Robot and electrode settings", "[robot] and [electrode]: every key"),
        ("config-planning.md", "Planner settings", "[planning]: every key and the effect of changing it"),
        ("config-entry-zone.md", "Allowed entry zone", "[entry_zone]: face, sinus, midline, skull base, ears"),
        ("config-no-go-and-soft-zones.md", "No-go and soft zones", "zone definition, all margins and weights, cost table"),
    ]),
    ("04-planner-app", "Planner app (desktop)", [
        ("install-and-run.md", "Install and run", "Python environment, run_app.bat, Windows exe, self-test"),
        ("main-window.md", "The main window", "slice views, 3D view, toolbar, side panel"),
        ("opening-a-patient.md", "Opening a patient", "required files, what is computed, files the app writes"),
        ("targets.md", "Targets", "add, rename, safety check, snap to a safe point"),
        ("target-regions.md", "Target regions", "drawing outlines, visual hull, saving"),
        ("layers-and-3d-view.md", "Layers and the 3D view", "layer groups, tags, colours, transparency"),
        ("planning-and-results.md", "Planning and results", "Plan / Stop, paths table, drawing on the slices, log messages"),
        ("export-to-headset.md", "Export to headset", "plan.json, paths.glb, brain model with the app's layers"),
    ]),
    ("05-path-planning", "Path planning", [
        ("loading-the-patient.md", "Loading the patient", "one grid for all scans, crop, resampling"),
        ("safety-maps.md", "Safety maps", "zone masks, midline, distance maps, clearance, soft map"),
        ("route-grid-and-entry-points.md", "Route grid and entry points", "2 mm cost grid, allowed skin points, normals, entry angle"),
        ("targets-check-and-region-tips.md", "Targets check and region tips", "best tip inside a region, target safety check"),
        ("planning-one-path.md", "Planning one path", "Dijkstra, entry candidates, straight entries, fitting the robot shape"),
        ("shape-optimisation.md", "Shape optimisation", "variables, cost, fines and weights, penalty continuation, examples"),
        ("final-check.md", "Final check and best result", "strict checks, result record, alternatives"),
        ("several-targets-on-one-path.md", "Several targets on one path", "group list, order test, exact arc shapes, pruning, time limit"),
        ("choosing-the-paths-milp.md", "Choosing the paths (MILP)", "why a MILP, formulation, conflicts, worked example"),
        ("electrode-contacts.md", "Electrode contacts", "contact positions, targets on contacts"),
    ]),
    ("06-headset-and-unity", "Headset and Unity", [
        ("hardware-and-software.md", "Hardware and software", "Quest 3, target headsets, Unity packages, scripts"),
        ("unity-project-setup.md", "Unity project setup", "project, packages, scene objects, patient files"),
        ("loading-the-patient-in-unity.md", "Loading the patient in Unity", "PatientLoader, build-safe materials, coordinates"),
        ("desktop-viewer.md", "Desktop viewer", "laptop viewer, edit landmarks, simulated registration"),
        ("running-on-the-quest.md", "Running on the Quest", "Meta Horizon Link, Android build, logs"),
        ("controls-and-help-panel.md", "Controls and help panel", "controller buttons, pen tip, panel"),
        ("landmark-registration.md", "Landmark registration", "procedure, Horn / Kabsch maths, FRE, ICP"),
        ("qr-head-tracking.md", "QR head tracking", "following the head, markers, settings, current status"),
        ("troubleshooting.md", "Troubleshooting", "pink model, no marker provider, other problems"),
    ]),
    ("07-tests-and-results", "Tests and results", [
        ("automatic-tests.md", "Automatic tests", "planner tests on a synthetic head, other tests"),
        ("results-ixi057.md", "Results on IXI057", "pipeline numbers, planner and headset results"),
    ]),
    ("08-project", "Project and repository", [
        ("repository-structure.md", "Repository structure", "every file and its documentation page"),
        ("limitations-and-roadmap.md", "Limitations and roadmap", "what is not done yet, next steps"),
        ("data-sources.md", "Data sources and safety", "test data, atlases, regulatory note"),
        ("updating-these-docs.md", "Updating these docs", "how the docs are organised and regenerated"),
    ]),
]


def put(text, key, block, top=False):
    """Replace the generated block <!-- nav:key --> ... <!-- /nav:key -->, or add it at the top / bottom."""
    start, end = f"<!-- nav:{key} -->", f"<!-- /nav:{key} -->"
    new = f"{start}\n{block}\n{end}"
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pat.search(text): return pat.sub(lambda _: new, text)
    return (new + "\n\n" + text) if top else (text.rstrip() + "\n\n" + new + "\n")


def edit(path, fn):
    with open(path, encoding="utf-8") as f: text = f.read()
    out = fn(text)
    if out != text:
        with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(out)


def main():
    order = []                                                  # reading order: category page, then its pages
    for folder, cat, pages in PAGES:
        order.append((folder, "README.md", cat))
        order += [(folder, f, t) for f, t, _ in pages]

    def rel(src_folder, folder, f):
        if src_folder == folder: return f
        return ("../" if src_folder else "") + (f"{folder}/{f}" if folder else f)

    # home page: all categories and pages
    lines = ["## Contents", ""]
    for i, (folder, cat, pages) in enumerate(PAGES, 1):
        lines.append(f"### {i}. [{cat}]({folder}/README.md)")
        lines.append("")
        lines += [f"- [{t}]({folder}/{f}) - {d}" for f, t, d in pages]
        lines.append("")
    edit(os.path.join(DOCS, "README.md"), lambda s: put(s, "contents", "\n".join(lines).rstrip()))

    for n, (folder, f, title) in enumerate(order):
        path = os.path.join(DOCS, folder, f)
        ci = next(i for i, (fo, _, _) in enumerate(PAGES) if fo == folder)
        cat = PAGES[ci][1]
        crumb = f"[Docs home](../README.md) › " + (f"**{cat}**" if f == "README.md" else f"[{cat}](README.md) › **{title}**")
        prev = order[n - 1] if n > 0 else None
        nxt = order[n + 1] if n + 1 < len(order) else None
        link = lambda o: f"[{o[2]}]({rel(folder, o[0], o[1])})"
        bar = " | ".join([f"← {link(prev)}" if prev else "← [Docs home](../README.md)",
                          "[↑ Docs home](../README.md)" if f == "README.md" else f"[↑ {cat}](README.md)",
                          f"{link(nxt)} →" if nxt else "[Docs home](../README.md) →"])

        def fix(s, crumb=crumb, bar=bar, f=f, ci=ci):
            s = put(s, "crumb", crumb, top=True)
            if f == "README.md":                                # category page: list of its pages
                folder_, cat_, pages = PAGES[ci]
                lst = ["## Pages in this category", ""] + [f"{k}. [{t}]({p}) - {d}" for k, (p, t, d) in enumerate(pages, 1)]
                s = put(s, "pages", "\n".join(lst))
            return put(s, "bar", "---\n" + bar)
        edit(path, fix)
    print(f"navigation updated: {len(order)} pages")


if __name__ == "__main__":
    main()
