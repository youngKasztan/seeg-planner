# SEEG Planner

Planowanie trajektorii elektrod SEEG na modelu mozgu pacjenta, wyswietlanym w Meta Quest 3.

**Status:** prototyp badawczy. Nie do uzytku klinicznego (wymaga certyfikacji MDR).

## Co robi pipeline

Surowe badania pacjenta -> segmentacja -> ekstrakcja warstw -> pakiet 3D gotowy do planowania.

```
python pipeline/run_pipeline.py --t1 T1.nii.gz --mra MRA.nii.gz \
    --dti_dir DTI/ --bvals bvals.txt --bvecs bvecs.txt \
    [--t1_gd T1_gd.nii.gz] [--ct CT.nii.gz --ct_postimplant] \
    --out wyniki/PACJENT --fastsurfer /sciezka/FastSurfer
```

| Krok | Skrypt | Wejscie | Wyjscie |
|---|---|---|---|
| 1. Segmentacja mozgu | FastSurfer (wywolywany z `run_pipeline.py`) | T1 | 95 obszarow atlasu, maska mozgu |
| 2. Maska glowy | `pipeline/head_mask.py` | T1 | skora |
| 3. Tetnice | `pipeline/vessels_mra.py` | TOF-MRA + T1 | maska tetnic (rejestracja MRA->T1, filtr Frangiego) |
| 3b. Drogi istoty bialej | `pipeline/tracts_dti.py` | DTI + T1 | korowo-rdzeniowa L/P, lukowata L, wzrokowa L/P (DIPY) |
| 3c. Zyly i zatoki | `pipeline/veins_ct1.py` | T1 przed + po gadolinie | zyly, zatoki (odjecie + Frangi w 2 skalach) - *niezwalidowane* |
| 3d. CT | `pipeline/ct_layers.py` | CT / CTA / CT po implantacji | kosc + grubosc, skora, tetnice z CTA, kontakty elektrod |
| Kora elokwentna | `pipeline/seeg_prep.py` | segmentacja (atlas DKT) | ruch, czucie, wzrok, sluch, mowa (mowa: zalozona lewa dominacja) |
| 4. Pakiet warstw | `pipeline/seeg_prep.py` | maski | siatki `.glb`, mapy odleglosci, `manifest.json` |
| 5. Podglad | `tools/render_preview.py` | pakiet | PNG z 3 widokami |

## Wyniki na pacjencie testowym IXI057

- Segmentacja: ~10 min na CPU (1-2 min z GPU)
- Tetnice vs reczna segmentacja ekspertow: **Dice 0.78** (czulosc 0.77, precyzja 0.80)
- Drogi istoty bialej (DTI 16 kierunkow, 1.75x1.75x2 mm): CST L 7.8 ml / P 6.6 ml, lukowata L 5.5 ml, wzrokowa L 12.1 ml / P 8.3 ml
  - konwencja znakow gradientow wybierana automatycznie (srednia dlugosc wlokien 48 mm vs ~25 mm dla zlych wariantow)
  - IXI: 17 wolumenow, tabela gradientow ma 16 - dopasowanie tensora wskazalo wolumeny 0-15 (residuum 0.051 vs 0.092)
- ~3 min traktografia na CPU

![Model 3D](docs/IXI057_preview.png)
![Tetnice vs eksperci](docs/IXI057_vessels_vs_experts.png)

## Brakujace / niezwalidowane

- Zyly i zatoki: kod gotowy (test na fantomie), brak publicznego pacjenta z T1 przed/po kontrascie -> [docs/veins_and_ct.md](docs/veins_and_ct.md)
- CT: kod gotowy (test na fantomie), nastepny krok: pacjent SEEG z CT (Brainstorm Epileptogenicity)
- Kora elokwentna z fMRI zamiast atlasu

## Testy

```
python tests/test_ct_phantom.py
python tests/test_veins_phantom.py
```

## Dane testowe

- IXI: https://brain-development.org/ixi-dataset/
- Reczne segmentacje naczyn IXI: https://zenodo.org/records/17393202
- Wagi FastSurfer: https://zenodo.org/records/10390573

Dane pacjentow nie sa przechowywane w repozytorium (`.gitignore`).
