// HeadMarkerTracker.cs - keeps the hologram on the real head when the person moves, using markers on the head.
//
// Idea: the markers are fixed rigidly to the head (headband; in the OR on the Mayfield clamp).
//   1. Landmark registration (LandmarkRegistration.cs) puts PatientRoot on the real head.
//   2. Calibrate(): for every head marker seen right now we store PatientRoot relative to that marker:
//        T_marker<-root = inverse(T_world<-marker) * T_world<-root
//   3. Every frame: T_world<-root = T_world<-marker(now) * T_marker<-root  (averaged over all visible head markers,
//      smoothed). When no head marker is visible the hologram stays where it was last.
// Head markers that were not visible during Calibrate() are added automatically the first time they are seen together
// with an already anchored marker (so a headband with 3 markers keeps working when the head turns).
//
// Marker sources (each one calls Report(id, pose) with world poses):
//   * AprilTagCameraSource (default): AprilTags (tagStandard41h12) found in the Quest passthrough camera image.
//     Ids are reported as "TAG-<n>". See AprilTagCameraSource.cs for the project settings it needs.
//   * QR codes through AR Foundation ARMarkerManager + "Unity OpenXR: Spatial Entities" (useQrCodes). Off by default:
//     on the test Quest 3 (runtime 209.161) the OpenXR runtime does not offer XR_EXT_spatial_entity, so there is no
//     marker subsystem. Payloads "SEEG-HEAD-<n>-<size>MM".
//
// printScale: the printer does not print at exactly 100 % (university printer: 100 mm -> 95 mm), so the real size
// of a marker is nominal * printScale. Used by the AprilTag pose estimation (tag size) and for the QR size check.
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
        [Tooltip("Marker ids starting with one of these prefixes are treated as head markers")]
        public string[] headPrefixes = { "TAG-", "SEEG-HEAD" };
        [Tooltip("Real printed size / nominal size. University printer: 95 mm instead of 100 mm -> 0.95")]
        public float printScale = 0.95f;
        [Tooltip("Smoothing time constant in seconds (0 = jump straight to the new pose)")]
        public float smoothing = 0.2f;
        [Tooltip("Position jumps larger than this (metres) are applied immediately instead of smoothed")]
        public float snapDistance = 0.10f;
        [Tooltip("A marker counts as visible if it was reported within this many seconds")]
        public float freshSeconds = 0.4f;
        [Tooltip("Detect AprilTags in the passthrough camera image (AprilTagCameraSource)")]
        public bool useAprilTags = true;
        [Tooltip("Use QR codes via AR Foundation markers (needs XR_EXT_spatial_entity on the headset)")]
        public bool useQrCodes = false;

        /// True while a calibration exists and is applied (hologram follows the head markers).
        public bool Following { get; private set; }
        /// Set by QuestControls while the hologram is carried by hand, so the tracker does not fight the grip.
        public bool Paused { get; set; }
        /// One status line from the active marker source (camera permission, detection rate, latency...).
        public string SourceStatus { get; set; } = "";

        class Obs
        {
            public Vector3 pos;
            public Quaternion rot;
            public float time = -100f;          // Time.time of the last report
            public float sizeM;                 // measured (QR) or assumed (AprilTag) edge length
            public float expectedM;             // expected real size from the printed sheet (0 = unknown)
        }

        struct Anchor { public Vector3 pos; public Quaternion rot; }   // T_marker<-root

        readonly Dictionary<string, Obs> observations = new();
        readonly Dictionary<string, Anchor> anchors = new();
        Vector3 smoothPos; Quaternion smoothRot = Quaternion.identity;
        string lastEvent = "";
        AprilTagCameraSource aprilSource;

        // ---------------------------------------------------------------- input from the marker sources

        /// A marker source saw marker `id` at this world pose now. sizeM/expectedM are only used for the status line.
        public void Report(string id, Vector3 worldPos, Quaternion worldRot, float sizeM = 0f, float expectedM = 0f)
        {
            if (string.IsNullOrEmpty(id)) return;
            if (!observations.TryGetValue(id, out var o))
            {
                o = new Obs();
                observations[id] = o;
                lastEvent = "new marker: " + id;
                Debug.Log("[HeadMarkerTracker] " + lastEvent);
            }
            o.pos = worldPos; o.rot = worldRot; o.time = Time.time; o.sizeM = sizeM; o.expectedM = expectedM;
        }

        bool IsHead(string id)
        {
            foreach (var p in headPrefixes)
                if (id.StartsWith(p, System.StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        bool Fresh(Obs o) => Time.time - o.time <= freshSeconds;

        void Start()
        {
            if (useAprilTags)
            {
                aprilSource = GetComponent<AprilTagCameraSource>();
                if (aprilSource == null) aprilSource = gameObject.AddComponent<AprilTagCameraSource>();
                aprilSource.tracker = this;
            }
            if (useQrCodes) StartQr();
        }

        // ---------------------------------------------------------------- anchoring

        /// Anchor the hologram (at its current pose) to all head markers visible now. Returns false if none is visible.
        public bool Calibrate()
        {
            if (loader == null || !loader.IsLoaded) return false;
            var root = loader.PatientRoot;
            anchors.Clear();
            int n = 0;
            foreach (var kv in observations)
            {
                if (!IsHead(kv.Key) || !Fresh(kv.Value)) continue;
                Store(kv.Key, kv.Value, root.position, root.rotation);
                n++;
            }
            if (n == 0) { lastEvent = "calibrate: no head marker visible"; return false; }
            smoothPos = root.position; smoothRot = root.rotation;
            Following = true;
            lastEvent = $"anchored to {n} head marker(s)";
            Debug.Log("[HeadMarkerTracker] " + lastEvent);
            return true;
        }

        /// Forget the anchoring (B = start again). The hologram no longer follows the markers.
        public void StopFollowing()
        {
            Following = false;
            anchors.Clear();
            lastEvent = "not anchored";
        }

        void Store(string id, Obs o, Vector3 rootPos, Quaternion rootRot)
        {
            var inv = Quaternion.Inverse(o.rot);
            anchors[id] = new Anchor { pos = inv * (rootPos - o.pos), rot = inv * rootRot };
        }

        void LateUpdate()
        {
            if (useQrCodes) PollQr();
            if (!Following || Paused || loader == null || !loader.IsLoaded) return;

            // target pose of PatientRoot = average over all visible anchored head markers
            Vector3 sumPos = Vector3.zero; Vector4 sumRot = Vector4.zero; int n = 0; Quaternion refRot = Quaternion.identity;
            foreach (var kv in observations)
            {
                if (!anchors.TryGetValue(kv.Key, out var a) || !Fresh(kv.Value)) continue;
                var o = kv.Value;
                Vector3 p = o.pos + o.rot * a.pos;
                Quaternion r = o.rot * a.rot;
                if (n == 0) refRot = r;
                if (Quaternion.Dot(refRot, r) < 0f) r = new Quaternion(-r.x, -r.y, -r.z, -r.w);   // same hemisphere
                sumPos += p; sumRot += new Vector4(r.x, r.y, r.z, r.w); n++;
            }
            if (n == 0) return;                                   // nothing visible: keep the last pose
            Vector3 targetPos = sumPos / n;
            sumRot.Normalize();
            var targetRot = new Quaternion(sumRot.x, sumRot.y, sumRot.z, sumRot.w);

            // head markers seen for the first time while the head is tracked: anchor them from the current target
            foreach (var kv in observations)
            {
                if (!IsHead(kv.Key) || anchors.ContainsKey(kv.Key) || !Fresh(kv.Value)) continue;
                Store(kv.Key, kv.Value, targetPos, targetRot);
                lastEvent = "added head marker " + kv.Key;
            }

            float k = smoothing <= 0f ? 1f : 1f - Mathf.Exp(-Time.deltaTime / smoothing);
            if ((targetPos - smoothPos).magnitude > snapDistance) k = 1f;
            smoothPos = Vector3.Lerp(smoothPos, targetPos, k);
            smoothRot = Quaternion.Slerp(smoothRot, targetRot, k);

            var root = loader.PatientRoot;
            if (root.parent != null) root.SetParent(null, true);
            root.SetPositionAndRotation(smoothPos, smoothRot);
        }

        /// One or two lines for the help panel.
        public string StatusLine()
        {
            var cam = Camera.main != null ? Camera.main.transform : null;
            var parts = new List<string>();
            foreach (var kv in observations)
            {
                var o = kv.Value;
                if (Time.time - o.time > 5f) continue;             // forget markers not seen for a while (display only)
                string name = kv.Key.Replace("SEEG-HEAD-", "QR");
                string dist = cam != null ? $" {(o.pos - cam.position).magnitude:F2}m" : "";
                string size = o.expectedM > 0f ? $" {o.sizeM * 1000f:F0}/{o.expectedM * 1000f:F1}mm" : "";
                parts.Add(name + dist + size + (Fresh(o) ? "" : " (lost)") + (anchors.ContainsKey(kv.Key) ? "*" : ""));
            }
            string seen = parts.Count == 0 ? "no marker seen" : string.Join("  ", parts);
            string mode = Following ? (Paused ? "PAUSED (grip)" : "FOLLOWING") : "not anchored";
            string src = SourceStatus;
            if (useQrCodes) src += (src == "" ? "" : " | ") + QrStatus();
            return $"Markers {mode}: {seen}\n<size=18>{src}\n{lastEvent}   (* = anchored)</size>";
        }

        // ================================================================ QR codes (AR Foundation markers), optional

        static readonly Regex SizeRe = new Regex(@"-(\d+(?:\.\d+)?)MM$", RegexOptions.IgnoreCase);
        const string ScenePermission = "com.oculus.permission.USE_SCENE";
        ARMarkerManager qrManager;
        readonly Dictionary<TrackableId, string> qrPayloads = new();
        float qrStart;

        /// Expected real edge length (metres) of a QR code with this payload, after the printer scale; 0 if unknown.
        public float ExpectedSizeM(string payload)
        {
            var m = SizeRe.Match(payload ?? "");
            if (!m.Success) return 0f;
            return float.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture) * 0.001f * printScale;
        }

        void StartQr()
        {
            qrStart = Time.time;
            var origin = FindAnyObjectByType<XROrigin>();
            if (origin == null) { lastEvent = "no XR Origin in the scene"; return; }
            qrManager = origin.GetComponent<ARMarkerManager>();
            if (qrManager == null) qrManager = origin.gameObject.AddComponent<ARMarkerManager>();
#if UNITY_ANDROID && !UNITY_EDITOR
            // Meta's runtime enumerates the spatial entity extensions only for apps with the spatial data permission,
            // and the Spatial Entities package never asks for it when its subsystem was not created. Ask here.
            if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(ScenePermission))
                UnityEngine.Android.Permission.RequestUserPermission(ScenePermission);
#endif
        }

        void PollQr()
        {
            if (qrManager == null || qrManager.subsystem == null) return;
            foreach (var m in qrManager.trackables)
            {
                if (m.trackingState != TrackingState.Tracking) continue;
                if (!qrPayloads.TryGetValue(m.trackableId, out var payload))
                {
                    payload = "";
                    if (m.markerType == XRMarkerType.QRCode || m.markerType == XRMarkerType.MicroQRCode)
                    {
                        var r = qrManager.TryGetStringData(m);          // allocates - done once per code
                        if (r.status.IsSuccess()) payload = r.value;
                    }
                    qrPayloads[m.trackableId] = payload;
                }
                if (payload == "") continue;
                Report(payload, m.transform.position, m.transform.rotation, m.size.x, ExpectedSizeM(payload));
            }
        }

        string QrStatus()
        {
            if (qrManager == null) return "QR: not started";
            if (qrManager.subsystem != null) return "QR: running";
            if (Time.time - qrStart < 3f) return "QR: starting...";
            bool entity = UnityEngine.XR.OpenXR.OpenXRRuntime.IsExtensionEnabled("XR_EXT_spatial_entity");
            return "QR: no marker provider (XR_EXT_spatial_entity " + (entity ? "on" : "MISSING") + ")";
        }
    }
}
