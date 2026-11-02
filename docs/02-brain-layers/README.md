<!-- nav:crumb -->
[Docs home](../README.md) › **Brain layers and patient data**
<!-- /nav:crumb -->

# Brain layers and patient data

How raw MRI exams become the 3D layers the planner and the headset use: brain regions, arteries, veins, nerve tracts, skull, skin. Every layer is labelled with its **origin** (measured in this patient, population prior, or estimate), so a guess is never shown as patient data.

<!-- nav:pages -->
## Pages in this category

1. [Running the pipeline](running-the-pipeline.md) - one command, required exams, steps, patient folder
2. [Segmentation and head mask](segmentation-and-head.md) - FastSurfer labels, head mask, anatomy layers
3. [Arteries from TOF-MRA](arteries.md) - registration, Frangi filter, thresholds, validation (Dice 0.78)
4. [White-matter tracts from DTI](white-matter-tracts.md) - tractography, automatic bvec check, the 9 tracts
5. [Veins, sinuses and CT](veins-sinuses-and-ct.md) - contrast-T1 subtraction, CT bone and contacts
6. [Sulci, skull and priors](sulci-skull-and-priors.md) - sulci, skull estimate, sagittal sinus rule, VENAT venous atlas
7. [Eloquent cortex](eloquent-cortex.md) - motor, sensory, visual, auditory and language areas from the atlas
8. [Layer catalogue](layer-catalogue.md) - every layer: source, origin, role in the planner, margin / weight
9. [Headset package and landmarks](headset-package-and-landmarks.md) - 3D scene, manifest, phantom, automatic face and ear landmarks
<!-- /nav:pages -->

<!-- nav:bar -->
---
← [Glossary](../01-overview/glossary.md) | [↑ Docs home](../README.md) | [Running the pipeline](running-the-pipeline.md) →
<!-- /nav:bar -->
