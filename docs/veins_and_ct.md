# Żyły, zatoki i CT – jak je sensownie dodać

## Żyły i zatoki opony twardej

**Wniosek:** jedyna wiarygodna droga to badanie, w którym krew żylna jest jasna – najlepiej **3D T1 po gadolinie** (standard przed SEEG w większości ośrodków). TOF-MRA celowo tłumi krew żylną, więc z naszego angio żył nie wyciągniemy.

| Opcja | Co daje | Ocena |
|---|---|---|
| **T1 przed + po gadolinie (odjęcie)** | zatoki + żyły korowe i mostowe, ~1 mm | **wybrana** – `pipeline/veins_ct1.py` |
| Wenografia MR (PC-MRV) / CT-wenografia | zatoki i duże żyły | dobra alternatywa, ten sam kod (wejście = obraz naczyniowy) |
| SWI | drobne żyły (ciemne) | dobra dla żył, słaba dla zatok; wymaga odwrócenia kontrastu |
| Atlas żylny nałożony na pacjenta | tylko przybliżone położenie dużych zatok | **nie do planowania** – żyły korowe są osobnicze |
| Zgadywanie z T1 bez kontrastu | nic pewnego | odrzucone |

**Jak działa `veins_ct1.py`:**
1. rejestracja T1+Gd → T1,
2. normalizacja jasności (mediana istoty białej = 1) i odjęcie: zostaje tylko to, co się wzmocniło,
3. filtr naczyniowy w dwóch skalach: zatoki (średnica 6–10 mm) i żyły (1–3 mm),
4. odjęcie tętnic z TOF (po gadolinie świecą też tętnice),
5. osobne warstwy `veins` i `sinuses`, obie krytyczne (mapa odległości).

**Status:** kod przetestowany na fantomie (`tests/test_veins_phantom.py`: zatoka wykryta w 70%, żyła w 100%). Brak publicznego pacjenta z T1 przed/po kontraście + TOF – walidacja czeka na dane.

## CT

CT w SEEG ma cztery zastosowania – każde to osobna warstwa lub wynik:

| Zastosowanie | Z czego | Wynik | Po co |
|---|---|---|---|
| **Kość czaszki** | CT (HU > 300) | `skull.nii.gz` + mapa grubości kości | punkt wejścia, kąt wiercenia, grubość kości na trajektorii |
| **Skóra** | CT (HU > −300) | `scalp.nii.gz` | dokładniejsza niż z MRI (brak zniekształceń) |
| **Tętnice z CTA** | CTA (HU 150–600 w czaszce, poza kością) | `arteries_cta.nii.gz` | gdy brak angio-MRI |
| **Elektrody po implantacji** | CT po zabiegu (HU > 2000) | `contacts.json` (położenia kontaktów w mm) | porównanie planu z wykonaniem, walidacja planera |

Dodatkowo w praktyce **rejestracja do robota / ramy stereotaktycznej** (np. Cirq, ROSA, Autoguide) odbywa się na CT – dlatego plan musi być w przestrzeni, którą da się przenieść na CT. U nas wszystko jest w przestrzeni T1, a CT jest do niej zarejestrowane sztywno (`ct_layers.py`), więc transformacja jest znana.

**Status:** kod przetestowany na fantomie (`tests/test_ct_phantom.py`: 8/8 kontaktów, grubość kości wykryta). Następny krok: prawdziwy pacjent SEEG z CT – samouczek Brainstorm „Epileptogenicity” (MRI przed + CT po implantacji; wymaga darmowego konta Brainstorm do pobrania).
