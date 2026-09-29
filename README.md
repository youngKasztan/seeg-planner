# SEEG Planner

Planowanie trajektorii elektrod SEEG na modelu mozgu pacjenta, wyswietlanym w Meta Quest 3.

**Status:** prototyp badawczy. Nie do uzytku klinicznego (wymaga certyfikacji MDR).

## Co robi pipeline

Surowe badania pacjenta -> segmentacja -> ekstrakcja warstw -> pakiet 3D gotowy do planowania.

```
python pipeline/run_pipeline.py --t1 T1.nii.gz --mra MRA.nii.gz --out wyniki/PACJENT --fastsurfer /sciezka/FastSurfer
```

| Krok | Skrypt | Wejscie | Wyjscie |
|---|---|---|---|
| 1. Segmentacja mozgu | FastSurfer (wywolywany z `run_pipeline.py`) | T1 | 95 obszarow atlasu, maska mozgu |
| 2. Maska glowy | `pipeline/head_mask.py` | T1 | skora |
| 3. Tetnice | `pipeline/vessels_mra.py` | TOF-MRA + T1 | maska tetnic (rejestracja MRA->T1, filtr Frangiego) |
| 4. Pakiet warstw | `pipeline/seeg_prep.py` | maski | siatki `.glb`, mapy odleglosci, `manifest.json` |
| 5. Podglad | `tools/render_preview.py` | pakiet | PNG z 3 widokami |

## Wyniki na pacjencie testowym IXI057

- Segmentacja: ~10 min na CPU (1-2 min z GPU)
- Tetnice vs reczna segmentacja ekspertow: **Dice 0.78** (czulosc 0.77, precyzja 0.80)

![Model 3D](docs/IXI057_preview.png)
![Tetnice vs eksperci](docs/IXI057_vessels_vs_experts.png)

## Brakujace warstwy

Zyly (T1 z kontrastem), drogi istoty bialej (DTI), kora elokwentna (fMRI / atlas), czaszka (CT).

## Dane testowe

- IXI: https://brain-development.org/ixi-dataset/
- Reczne segmentacje naczyn IXI: https://zenodo.org/records/17393202
- Wagi FastSurfer: https://zenodo.org/records/10390573

Dane pacjentow nie sa przechowywane w repozytorium (`.gitignore`).
