<!-- nav:crumb -->
[Docs home](../README.md) › [Headset and Unity](README.md) › **Running on the Quest**
<!-- /nav:crumb -->

# Running on the Quest

> **In short:** two ways: Play mode streamed to the headset over Meta Horizon Link (fast for testing, files read from the PC), or an Android app built and installed on the headset (passthrough always works).

## A. Play mode over Meta Horizon Link

1. PC: Meta Horizon Link app -> Settings -> General -> OpenXR Runtime: Meta Horizon Link; Developer runtime features on; passthrough over Link on (if the app version offers it - v83+ no longer has the Beta tab, then use B).
2. XR Plug-in Management -> **Windows** tab: OpenXR on, Meta Quest feature group, Touch controller profile.
3. Headset: Quick Settings -> Link -> connect; press **Play** in Unity. The patient files are read from the Package Folder on the PC.

## B. Android app on the headset

1. Unity Hub -> Installs -> Unity 6.3 -> Add modules: **Android Build Support** (+ OpenJDK, Android SDK & NDK).
2. Headset in **Developer Mode** (Meta Horizon phone app of the headset's admin account -> Devices -> Developer Mode).
3. Patient files into `Assets/StreamingAssets/patient/` ([Unity project setup](unity-project-setup.md)).
4. File -> Build Profiles -> Android -> Switch Platform. XR Plug-in Management -> **Android** tab: OpenXR, Meta Quest feature group, Touch controller profile; Project Validation -> Fix All.
5. Headset on USB, allow USB debugging in the headset; Build Profiles -> Android -> Run Device = Quest 3 -> **Build And Run**.

App package name: `com.kubabanaszek.seegplanner`.

## Logs from the headset

`adb` ships with Unity: `C:\Program Files\Unity\Hub\Editor\6000.3.25f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe`. In `cmd`:

```
set ADB="C:\Program Files\Unity\Hub\Editor\6000.3.25f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe"
%ADB% logcat -c
%ADB% logcat -s Unity > C:\Users\MSI\Desktop\UnityKopia\quest_log1.txt
```

Recording the headset view: casting at oculus.com/casting in the browser + Windows Game Bar (Win+Alt+R).

<!-- nav:bar -->
---
← [Desktop viewer](desktop-viewer.md) | [↑ Headset and Unity](README.md) | [Controls and help panel](controls-and-help-panel.md) →
<!-- /nav:bar -->
