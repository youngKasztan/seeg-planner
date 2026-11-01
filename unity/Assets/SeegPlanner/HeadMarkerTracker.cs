// HeadMarkerTracker.cs - keeps the hologram on the real head when the person moves, using QR codes on the head.
//
// Idea: the QR code(s) are fixed rigidly to the head (headband; in the OR on the Mayfield clamp).
//   1. Landmark registration (LandmarkRegistration.cs) puts PatientRoot on the real head.
//   2. Calibrate(): for every head QR code seen right now we store PatientRoot relative to that code:
//        T_marker<-root = inverse(T_world<-marker) * T_world<-root
//   3. Every frame: T_world<-root = T_world<-marker(now) * T_marker<-root  (averaged over all visible head codes,
//      smoothed). When no head code is visible the hologram stays where it was last.
// Head codes that were not visible during Calibrate() are added automatically the first time they are seen together
// with an already calibrated code (so a headband with 3 codes keeps working when the head turns).
//
// Marker detection: AR Foundation ARMarkerManager (AR Foundation >= 6.4). On Meta Quest the provider is the package
// "Unity OpenXR: Spatial Entities" (com.unity.xr.spatialentities-openxr), Meta Horizon OS supports QR codes only.
// Without a provider the tracker does nothing and reports "no marker provider".
//
// Project Settings > XR Plug-in Management > OpenXR (Android): enable the "Spatial Entities" feature group and
// "Spatial Entities: Markers" only; in its gear window enable QR Code detection, "Markers are fixed size" with the
// REAL printed side length (50 mm code * 0.95 = 0.0475 m) and leave "Markers are static" OFF (the head moves).
//
// Payload convention (see the printed sheet): "SEEG-HEAD-<n>-<size>MM", e.g. "SEEG-HEAD-1-50MM".
// printScale: the printer does not print at exactly 100 % (university printer: 100 mm -> 95 mm), so the real size
// of a code is nominal * printScale. The runtime measures the code size itself (ARMarker.size); the expected size is
// shown next to it on the help panel as a check of the tracking and is used by any size-dependent code later.
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;

namespace SeegPlanner
{
    public class HeadMarkerTracker : MonoBehaviour
    {
        public PatientLoader loader;
        [Tooltip("Only QR codes whose text starts with this prefix are treated as head markers")]
        public string headPrefix = "SEEG-HEAD";
        [Tooltip("Real printed size / nominal size. University printer: 95 mm instead of 100 mm -> 0.95")]
        public float printScale = 0.95f;
        [Tooltip("Smoothing time constant in seconds (0 = jump straight to the new pose)")]
        public float smoothing = 0.15f;
        [Tooltip("Position jumps larger than this (metres) are applied immediately instead of smoothed")]
        public float snapDistance = 0.10f;

        /// True while a calibration exists and is applied (hologram follows the head codes).
        public bool Following { get; private set; }
        /// Set by QuestControls while the hologram is carried by hand, so the tracker does not fight the grip.
        public bool Paused { get; set; }

        class Entry
        {
            public string payload;
            public float nominalMm;                 // from the payload ("...-50MM"), 0 if unknown
            public float lastSeen = -1f;            // Time.time of the last added/updated event
        }

        struct Anchor { public Vector3 pos; public Quaternion rot; }   // T_marker<-root

        readonly Dictionary<TrackableId, Entry> entries = new();
        // Anchors are kept per payload (not per TrackableId): the runtime may drop a code that left the view and
        // report it again later under a new id - it must still be anchored.
        readonly Dictionary<string, Anchor> anchors = new();
        ARMarkerManager manager;
        Vector3 smoothPos; Quaternion smoothRot = Quaternion.identity;
        float startTime;
        string lastEvent = "";

        static readonly Regex SizeRe = new Regex(@"-(\d+(?:\.\d+)?)MM$", RegexOptions.IgnoreCase);

        /// Expected real edge length (metres) of a code with this payload, after the printer scale; 0 if unknown.
        public float ExpectedSizeM(string payload)
        {
            var m = SizeRe.Match(payload ?? "");
            if (!m.Success) return 0f;
            return float.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture) * 0.001f * printScale;
        }

        void Start()
        {
            startTime = Time.time;
            var origin = FindAnyObjectByType<XROrigin>();
            if (origin == null) { lastEvent = "no XR Origin in the scene"; return; }
            manager = origin.GetComponent<ARMarkerManager>();
            if (manager == null) manager = origin.gameObject.AddComponent<ARMarkerManager>();
            manager.trackablesChanged.AddListener(OnMarkersChanged);
#if UNITY_ANDROID && !UNITY_EDITOR
            // Meta's runtime does not even offer the spatial entity OpenXR extensions (XR_EXT_spatial_entity, ...)
            // to an app without the spatial data permission, so the Spatial Entities package never creates its marker
            // subsystem and therefore never asks for the permission itself. Ask here; the extensions are enumerated
            // when the OpenXR instance is created, so after the first "Allow" the app must be started once more.
            if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(ScenePermission))
            {
                var cb = new UnityEngine.Android.PermissionCallbacks();
                cb.PermissionGranted += _ => { permissionJustGranted = true; };
                cb.PermissionDenied += _ => { lastEvent = "spatial data permission denied"; };
                UnityEngine.Android.Permission.RequestUserPermission(ScenePermission, cb);
            }
#endif
        }

        const string ScenePermission = "com.oculus.permission.USE_SCENE";
        bool permissionJustGranted;

        void OnDestroy()
        {
            if (manager != null) manager.trackablesChanged.RemoveListener(OnMarkersChanged);
        }

        void OnMarkersChanged(ARTrackablesChangedEventArgs<ARMarker> args)
        {
            foreach (var m in args.added) Seen(m);
            foreach (var m in args.updated) Seen(m);
            foreach (var kv in args.removed) entries.Remove(kv.Key);
        }

        void Seen(ARMarker m)
        {
            if (!entries.TryGetValue(m.trackableId, out var e))
            {
                string text = null;
                if (m.markerType == XRMarkerType.QRCode || m.markerType == XRMarkerType.MicroQRCode)
                {
                    var r = manager.TryGetStringData(m);             // allocates - done once per code
                    if (r.status.IsSuccess()) text = r.value;
                }
                e = new Entry { payload = text ?? "" };
                var sm = SizeRe.Match(e.payload);
                if (sm.Success) e.nominalMm = float.Parse(sm.Groups[1].Value, CultureInfo.InvariantCulture);
                entries[m.trackableId] = e;
                lastEvent = "new code: " + (text ?? "(no text)");
                Debug.Log($"[HeadMarkerTracker] {lastEvent}, measured size {m.size.x * 1000f:F1} mm");
            }
            e.lastSeen = Time.time;
        }

        bool IsHead(Entry e) => e.payload.StartsWith(headPrefix, System.StringComparison.OrdinalIgnoreCase);

        static bool Tracked(ARMarker m) => m != null && m.trackingState == TrackingState.Tracking;

        /// Anchor the hologram (at its current pose) to all head codes visible now. Returns false if none is visible.
        public bool Calibrate()
        {
            if (manager == null || loader == null || !loader.IsLoaded) return false;
            var root = loader.PatientRoot;
            anchors.Clear();
            int n = 0;
            foreach (var kv in entries)
            {
                var e = kv.Value; var m = manager.GetMarker(kv.Key);
                if (!IsHead(e) || !Tracked(m)) continue;
                Store(e, m.transform, root.position, root.rotation);
                n++;
            }
            if (n == 0) { lastEvent = "calibrate: no head code visible"; return false; }
            smoothPos = root.position; smoothRot = root.rotation;
            Following = true;
            lastEvent = $"anchored to {n} head code(s)";
            Debug.Log("[HeadMarkerTracker] " + lastEvent);
            return true;
        }

        /// Forget the anchoring (B = start again). The hologram no longer follows the codes.
        public void StopFollowing()
        {
            Following = false;
            anchors.Clear();
            lastEvent = "not anchored";
        }

        void Store(Entry e, Transform marker, Vector3 rootPos, Quaternion rootRot)
        {
            var inv = Quaternion.Inverse(marker.rotation);
            anchors[e.payload] = new Anchor { pos = inv * (rootPos - marker.position), rot = inv * rootRot };
        }

        bool Anchored(Entry e) => IsHead(e) && anchors.ContainsKey(e.payload);

        void LateUpdate()
        {
            if (!Following || Paused || manager == null || loader == null || !loader.IsLoaded) return;

            // target pose of PatientRoot = average over all visible calibrated head codes
            Vector3 sumPos = Vector3.zero; Vector4 sumRot = Vector4.zero; int n = 0; Quaternion refRot = Quaternion.identity;
            foreach (var kv in entries)
            {
                var e = kv.Value; if (!Anchored(e)) continue;
                var m = manager.GetMarker(kv.Key); if (!Tracked(m)) continue;
                var a = anchors[e.payload];
                Vector3 p = m.transform.position + m.transform.rotation * a.pos;
                Quaternion r = m.transform.rotation * a.rot;
                if (n == 0) refRot = r;
                if (Quaternion.Dot(refRot, r) < 0f) r = new Quaternion(-r.x, -r.y, -r.z, -r.w);   // same hemisphere
                sumPos += p; sumRot += new Vector4(r.x, r.y, r.z, r.w); n++;
            }
            if (n == 0) return;                                   // nothing visible: keep the last pose
            Vector3 targetPos = sumPos / n;
            sumRot.Normalize();
            var targetRot = new Quaternion(sumRot.x, sumRot.y, sumRot.z, sumRot.w);

            // head codes seen for the first time while the head is tracked: calibrate them from the current target
            foreach (var kv in entries)
            {
                var e = kv.Value; if (!IsHead(e) || Anchored(e)) continue;
                var m = manager.GetMarker(kv.Key); if (!Tracked(m)) continue;
                Store(e, m.transform, targetPos, targetRot);
                lastEvent = "added head code " + e.payload;
            }

            float k = smoothing <= 0f ? 1f : 1f - Mathf.Exp(-Time.deltaTime / smoothing);
            if ((targetPos - smoothPos).magnitude > snapDistance) k = 1f;
            smoothPos = Vector3.Lerp(smoothPos, targetPos, k);
            smoothRot = Quaternion.Slerp(smoothRot, targetRot, k);

            var root = loader.PatientRoot;
            if (root.parent != null) root.SetParent(null, true);
            root.SetPositionAndRotation(smoothPos, smoothRot);
        }

        static readonly string[] RequiredExtensions =
            { "XR_EXT_future", "XR_EXT_spatial_entity", "XR_EXT_spatial_marker_tracking" };
        string diagnosis;

        /// Why there is no marker subsystem: Spatial Entities creates it only if the headset's OpenXR runtime offers
        /// all three extensions. Shows which are offered (available) / switched on (enabled) and the runtime version.
        string RuntimeDiagnosis()
        {
            if (diagnosis != null) return diagnosis;
            var available = new HashSet<string>(UnityEngine.XR.OpenXR.OpenXRRuntime.GetAvailableExtensions() ?? new string[0]);
            var parts = new List<string>();
            foreach (var ext in RequiredExtensions)
            {
                string state = UnityEngine.XR.OpenXR.OpenXRRuntime.IsExtensionEnabled(ext) ? "on"
                             : available.Contains(ext) ? "available, off" : "MISSING";
                parts.Add(ext.Replace("XR_EXT_", "") + ": " + state);
            }
            string perm = "?";
#if UNITY_ANDROID && !UNITY_EDITOR
            perm = UnityEngine.Android.Permission.HasUserAuthorizedPermission(ScenePermission) ? "yes" : "NO";
#endif
            diagnosis = string.Join(", ", parts) + "\nruntime " + UnityEngine.XR.OpenXR.OpenXRRuntime.name + " " +
                        UnityEngine.XR.OpenXR.OpenXRRuntime.version + ", spatial data permission: " + perm;
            Debug.Log("[HeadMarkerTracker] no marker subsystem: " + diagnosis.Replace("\n", " | "));
            // full list of spatial/scene/marker related extensions the runtime offers (for logcat -s Unity)
            var related = new List<string>();
            foreach (var ext in available)
            {
                string l = ext.ToLowerInvariant();
                if (l.Contains("spatial") || l.Contains("marker") || l.Contains("scene") || l.Contains("future"))
                    related.Add(ext + (UnityEngine.XR.OpenXR.OpenXRRuntime.IsExtensionEnabled(ext) ? "(on)" : ""));
            }
            related.Sort();
            Debug.Log($"[HeadMarkerTracker] runtime offers {available.Count} extensions; related: " + string.Join(" ", related));
            return diagnosis;
        }

        /// One or two lines for the help panel.
        public string StatusLine()
        {
            if (manager == null) return "QR: " + (lastEvent == "" ? "not started" : lastEvent);
            if (manager.subsystem == null && permissionJustGranted)
                return "QR: spatial data permission granted.\n<b>Close the app and start it again</b> to enable QR tracking.";
            if (manager.subsystem == null)
                return Time.time - startTime < 3f ? "QR: starting..." : "QR: no marker provider\n<size=18>" + RuntimeDiagnosis() + "</size>";
            var parts = new List<string>();
            foreach (var kv in entries)
            {
                var e = kv.Value; var m = manager.GetMarker(kv.Key);
                string name = e.payload == "" ? "?" : e.payload.Replace(headPrefix + "-", "");
                string state = Tracked(m) ? "" : " (lost)";
                string size = m != null ? $" {m.size.x * 1000f:F0}" : "";
                float exp = ExpectedSizeM(e.payload);
                if (exp > 0f) size += $"/{exp * 1000f:F1}mm";
                parts.Add(name + size + state + (Anchored(e) ? "*" : ""));
            }
            string seen = parts.Count == 0 ? "no code seen" : string.Join("  ", parts);
            string mode = Following ? (Paused ? "PAUSED (grip)" : "FOLLOWING") : "not anchored";
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(ScenePermission))
                mode += ", permission: no";
#endif
            return $"QR {mode}: {seen}\n<size=18>{lastEvent}   (size measured/expected, * = anchored)</size>";
        }
    }
}
