// QuestControls.cs - use the patient model on a Meta Quest (passthrough), with the Touch controllers.
// Works in Play mode over Meta Horizon Link and in an Android build. Does nothing without a headset.
//
//   Right trigger : record the current landmark at the red pen tip in front of the right controller
//   Left Y        : skip the current landmark (e.g. the eye corners)
//   Right B       : start the registration again
//   Right A       : hologram on / off (to look at the real head)
//   Left X        : skin (scalp) layer on / off, to check the fit
//   Left grip     : hold to carry the hologram with the left controller (manual placement)
//
// The help text floats above the left controller. Registration itself: LandmarkRegistration.cs (>= 3 landmarks).
using UnityEngine;
using UnityEngine.XR;
using Newtonsoft.Json.Linq;

namespace SeegPlanner
{
    public class QuestControls : MonoBehaviour
    {
        public PatientLoader loader;
        public LandmarkRegistration registration;
        [Tooltip("Pen tip relative to the right controller (metres; x right, y up, z forward)")]
        public Vector3 tipOffset = new Vector3(0f, -0.02f, 0.08f);
        [Tooltip("At start the hologram is placed this far in front of the headset")]
        public float startDistance = 0.5f;

        Transform tip, label;
        TextMesh text;
        bool placed, hologramOn = true, scalpOn;
        bool prevTrig, prevA, prevB, prevX, prevY, prevGrip;
        Vector3 grabPos; Quaternion grabRot;
        string status = "";

        void Start()
        {
            tip = MakeSphere("QuestPenTip", 0.008f, Color.red);
            label = MakeLabel();
            tip.gameObject.SetActive(false); label.gameObject.SetActive(false);
        }

        void Update()
        {
            if (!XRSettings.isDeviceActive || loader == null || !loader.IsLoaded || registration == null) return;
            var cam = Camera.main; if (cam == null) return;
            Transform space = cam.transform.parent;                 // XR Origin "Camera Offset" = tracking space
            if (!placed) { PlaceInFront(cam.transform); placed = true; scalpOn = IsVisible("scalp"); }

            var right = InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            var left = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            bool rOk = Pose(right, space, out Vector3 rp, out Quaternion rr);
            bool lOk = Pose(left, space, out Vector3 lp, out Quaternion lr);

            tip.gameObject.SetActive(rOk);
            if (rOk) tip.position = rp + rr * tipOffset;

            if (Pressed(right, CommonUsages.triggerButton, ref prevTrig) && rOk) Capture();
            if (Pressed(right, CommonUsages.secondaryButton, ref prevB)) { registration.ResetCapture(); status = "Registration reset - start again"; }
            if (Pressed(right, CommonUsages.primaryButton, ref prevA))
            {
                hologramOn = !hologramOn; loader.PatientRoot.gameObject.SetActive(hologramOn);
            }
            if (Pressed(left, CommonUsages.secondaryButton, ref prevY))
            {
                string n = registration.NextLandmark;
                if (n != null) { registration.Skip(); status = "Skipped " + n; }
            }
            if (Pressed(left, CommonUsages.primaryButton, ref prevX)) { scalpOn = !scalpOn; loader.SetLayerVisible("scalp", scalpOn); }
            Carry(left, lOk, lp, lr);

            label.gameObject.SetActive(lOk);
            if (lOk)
            {
                label.position = lp + lr * new Vector3(0f, 0.07f, 0.03f);
                label.rotation = Quaternion.LookRotation(label.position - cam.transform.position);
                text.text = Message();
            }
        }

        void Capture()
        {
            string n = registration.NextLandmark;
            if (n == null) { status = "All landmarks done - B to start again"; return; }
            registration.CaptureWorld(tip.position);
            status = registration.CapturedCount >= 3
                ? $"{Nice(n)} recorded. Fit error (FRE) {registration.LastFreMm:F1} mm"
                : $"{Nice(n)} recorded ({registration.CapturedCount} of at least 3)";
        }

        string Message()
        {
            string n = registration.NextLandmark;
            string task = n == null ? "All landmarks done." : $"Touch: {Nice(n)}\n{Hint(n)}\nTrigger = record   Y = skip";
            return $"{task}\n{status}\nA = hologram   X = skin   B = restart\nLeft grip = carry the brain";
        }

        static string Nice(string n) => n.Replace('_', ' ');

        string Hint(string n)
        {
            JToken h = loader.Manifest["landmarks"]?[n]?["touch_hint"];
            return h != null ? (string)h : "";
        }

        bool IsVisible(string layer) => loader.Layers.TryGetValue(layer, out var go) && go.activeSelf;

        void PlaceInFront(Transform cam)
        {
            var root = loader.PatientRoot;
            Vector3 f = cam.forward; f.y = 0f;
            if (f.sqrMagnitude < 1e-4f) f = Vector3.forward;
            f.Normalize();
            root.SetParent(null, true);
            root.position = cam.position + f * startDistance;
            root.rotation = Quaternion.LookRotation(-f);            // the face (model +z) looks at the user
        }

        void Carry(InputDevice left, bool ok, Vector3 p, Quaternion r)
        {
            bool grip = ok && left.TryGetFeatureValue(CommonUsages.gripButton, out bool g) && g;
            var root = loader.PatientRoot;
            if (grip && !prevGrip)
            {
                grabRot = Quaternion.Inverse(r) * root.rotation;
                grabPos = Quaternion.Inverse(r) * (root.position - p);
                root.SetParent(null, true);
            }
            if (grip) { root.rotation = r * grabRot; root.position = p + r * grabPos; }
            prevGrip = grip;
        }

        static bool Pose(InputDevice d, Transform space, out Vector3 p, out Quaternion r)
        {
            p = Vector3.zero; r = Quaternion.identity;
            if (!d.isValid || !d.TryGetFeatureValue(CommonUsages.devicePosition, out p) ||
                !d.TryGetFeatureValue(CommonUsages.deviceRotation, out r)) return false;
            if (space != null) { p = space.TransformPoint(p); r = space.rotation * r; }
            return true;
        }

        static bool Pressed(InputDevice d, InputFeatureUsage<bool> usage, ref bool prev)
        {
            bool now = d.isValid && d.TryGetFeatureValue(usage, out bool v) && v;
            bool edge = now && !prev; prev = now; return edge;
        }

        static Transform MakeSphere(string name, float size, Color c)
        {
            var s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            s.name = name; Destroy(s.GetComponent<Collider>());
            s.transform.localScale = Vector3.one * size;
            var m = s.GetComponent<Renderer>().material; m.color = c; m.SetColor("_BaseColor", c);
            return s.transform;
        }

        Transform MakeLabel()
        {
            var go = new GameObject("QuestHelpText");
            text = go.AddComponent<TextMesh>();
            Font f = null;
            try { f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
            if (f == null) try { f = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { }
            if (f != null) { text.font = f; go.GetComponent<MeshRenderer>().material = f.material; }
            text.fontSize = 64; text.characterSize = 0.0025f;
            text.anchor = TextAnchor.LowerCenter; text.alignment = TextAlignment.Center; text.color = Color.white;
            return go.transform;
        }
    }
}
