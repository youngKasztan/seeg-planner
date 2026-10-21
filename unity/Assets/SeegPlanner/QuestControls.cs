// QuestControls.cs - use the patient model on a Meta Quest (passthrough), with the Touch controllers.
// Works in Play mode over Meta Horizon Link and in an Android build. Does nothing without a headset.
//
//   Right trigger : record the current landmark at the red pen tip in front of the right controller
//   Left Y        : skip the current landmark (e.g. the eye corners); left thumbstick click does the same
//   Right B       : start again - clear all touched points, hologram back in front of you
//   Right A       : hologram on / off (to look at the real head)
//   Left X        : skin (scalp) layer on / off, to check the fit
//   Left grip     : hold to carry the hologram with the left controller (manual placement)
//
// The help panel floats above the left controller (in front of you when the left controller is not tracked).
// It is a world-space uGUI canvas: UI/Default and the built-in font are always in a player build
// (TextMesh's font shader is not, so the old help text was invisible on the headset).
// Registration itself: LandmarkRegistration.cs (>= 3 landmarks).
using UnityEngine;
using UnityEngine.UI;
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
        [Tooltip("At start (and after B) the hologram is placed this far in front of the headset")]
        public float startDistance = 0.5f;
        [Tooltip("Width of the help panel in metres")]
        public float panelWidth = 0.24f;

        Transform tip, panel;
        Text text;
        bool placed, hologramOn = true, scalpOn, scalpDefault;
        bool prevTrig, prevA, prevB, prevX, prevY, prevStick, prevGrip;
        string lastButton = "-";               // shown on the panel, so a button that does nothing is easy to spot
        Vector3 grabPos; Quaternion grabRot;
        string status = "";

        const float PanelPx = 600f;                 // canvas width in UI pixels; scaled to panelWidth metres

        void Start()
        {
            tip = MakeSphere("QuestPenTip", 0.008f, Color.red);
            panel = MakePanel();
            tip.gameObject.SetActive(false); panel.gameObject.SetActive(false);
        }

        void Update()
        {
            if (!XRSettings.isDeviceActive || loader == null || !loader.IsLoaded || registration == null) return;
            var cam = Camera.main; if (cam == null) return;
            Transform space = cam.transform.parent;                 // XR Origin "Camera Offset" = tracking space
            if (!placed)
            {
                PlaceInFront(cam.transform); placed = true;
                scalpOn = scalpDefault = IsVisible("scalp");
                status = "Ready. Start with the first point.";
            }

            var right = InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            var left = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            bool rOk = Pose(right, space, out Vector3 rp, out Quaternion rr);
            bool lOk = Pose(left, space, out Vector3 lp, out Quaternion lr);

            tip.gameObject.SetActive(rOk);
            if (rOk) tip.position = rp + rr * tipOffset;

            if (Pressed(right, CommonUsages.triggerButton, ref prevTrig) && rOk) { lastButton = "right trigger"; Capture(); }
            if (Pressed(right, CommonUsages.secondaryButton, ref prevB)) { lastButton = "B"; StartOver(cam.transform); }
            if (Pressed(right, CommonUsages.primaryButton, ref prevA))
            {
                lastButton = "A"; hologramOn = !hologramOn; loader.PatientRoot.gameObject.SetActive(hologramOn);
            }
            bool y = Pressed(left, CommonUsages.secondaryButton, ref prevY);
            bool stick = Pressed(left, CommonUsages.primary2DAxisClick, ref prevStick);
            if (y || stick)
            {
                lastButton = y ? "Y" : "left stick";
                string n = registration.NextLandmark;
                if (n != null) { registration.Skip(); status = "Skipped: " + Nice(n); }
                else status = "Nothing to skip - all points done. B = start again.";
            }
            if (Pressed(left, CommonUsages.primaryButton, ref prevX))
            {
                lastButton = "X"; scalpOn = !scalpOn; loader.SetLayerVisible("scalp", scalpOn);
            }
            Carry(left, lOk, lp, lr);

            // help panel: above the left controller, otherwise low in front of the face
            panel.gameObject.SetActive(true);
            Vector3 f = cam.transform.forward;
            panel.position = lOk ? lp + lr * new Vector3(0f, 0.06f, 0.02f)
                                 : cam.transform.position + f * 0.6f - cam.transform.up * 0.18f;
            panel.rotation = Quaternion.LookRotation(panel.position - cam.transform.position, cam.transform.up);
            text.text = Message();
        }

        /// B: back to the beginning - forget all touched points, hologram visible and in front of the user again.
        void StartOver(Transform cam)
        {
            registration.ResetCapture();
            hologramOn = true; loader.PatientRoot.gameObject.SetActive(true);
            scalpOn = scalpDefault; loader.SetLayerVisible("scalp", scalpOn);
            PlaceInFront(cam);
            status = "Started again - touch the points from the beginning.";
        }

        void Capture()
        {
            string n = registration.NextLandmark;
            if (n == null) { status = "All points done. Press B to start again."; return; }
            registration.CaptureWorld(tip.position);
            status = registration.CapturedCount >= 3
                ? $"Recorded: {Nice(n)}. Fit error (FRE) {registration.LastFreMm:F1} mm"
                : $"Recorded: {Nice(n)} ({registration.CapturedCount} of at least 3)";
        }

        string Message()
        {
            string n = registration.NextLandmark;
            string task = n == null
                ? "<b>All points done.</b>\nCheck the fit: X = skin on/off, A = hologram on/off."
                : $"<b>Touch: {Nice(n).ToUpper()}</b>\n{Hint(n)}\n(patient's own left / right)\nRight trigger = record    Y (or left stick click) = skip";
            return $"{task}\n\n<i>{status}</i>\n\n" +
                   "A = hologram on/off    X = skin on/off\nB = START AGAIN    Left grip = move the brain\n" +
                   $"<size=18>last button: {lastButton}</size>";
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
            root.localScale = Vector3.one;
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
            var mat = PatientLoader.SolidMaterial(c);                         // default material is pink in a headset build
            if (mat != null) s.GetComponent<Renderer>().sharedMaterial = mat;
            else { var m = s.GetComponent<Renderer>().material; m.color = c; m.SetColor("_BaseColor", c); }
            return s.transform;
        }

        /// World-space canvas: dark rounded-less box with white text, anchored at its bottom centre.
        Transform MakePanel()
        {
            var go = new GameObject("QuestHelpPanel");
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvas.sortingOrder = 100;
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(PanelPx, 330f);
            rt.pivot = new Vector2(0.5f, 0f);
            go.transform.localScale = Vector3.one * (panelWidth / PanelPx);

            var bg = new GameObject("Background").AddComponent<Image>();
            bg.transform.SetParent(go.transform, false);
            bg.color = new Color(0f, 0f, 0f, 0.75f);
            Stretch(bg.rectTransform, 0f);

            text = new GameObject("Text").AddComponent<Text>();
            text.transform.SetParent(go.transform, false);
            Stretch(text.rectTransform, 16f);
            Font f = null;
            try { f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
            if (f == null) try { f = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { }
            text.font = f;
            text.fontSize = 26;
            text.supportRichText = true;
            text.alignment = TextAnchor.MiddleCenter;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            text.color = Color.white;
            return go.transform;
        }

        static void Stretch(RectTransform r, float margin)
        {
            r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one;
            r.offsetMin = new Vector2(margin, margin); r.offsetMax = new Vector2(-margin, -margin);
        }
    }
}
