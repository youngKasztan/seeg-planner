// DesktopViewer.cs - look at the patient model on a laptop, without a headset (Play mode in the Unity Editor).
//   left mouse drag = rotate, right drag = pan, wheel or the Zoom slider = zoom
//   panel on the left: switch layers on/off in the same groups as the planner app (No-go zones, Soft zones,
//   Anatomy, Head; origin shown: patient / PRIOR / ESTIMATE / atlas function), robot paths on/off,
//   show the 5 alignment landmarks, and run a SIMULATED registration: a virtual head is placed at a random pose,
//   the 5 landmarks are "touched" with ~2 mm noise, and LandmarkRegistration moves the hologram onto it.
//   The panel then shows FRE and the target error at the left hippocampus.
//   "Edit landmarks": pick a landmark in the list, click on the skin to move it there; it is saved to
//   headset_manifest.json, so the corrected points are used on the headset too.
// Works with both the new Input System and the old Input Manager.
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SeegPlanner
{
    public class DesktopViewer : MonoBehaviour
    {
        public PatientLoader loader;
        public LandmarkRegistration registration;
        public float distance = 0.45f;
        const float PanelWidth = 330f, MinDist = 0.05f, MaxDist = 3f;

        float yaw = 180f, pitch = 10f;        // start looking at the face
        Vector3 panOffset;
        Vector2 scroll;
        bool showLandmarks = true;
        readonly List<GameObject> markers = new();
        readonly Dictionary<string, bool> visible = new();
        string simResult = "";
        Transform virtualHead;

        bool editMode;
        string editing;
        Vector2 pressPos;
        readonly Dictionary<string, GameObject> markerByName = new();

        // layer groups as in the planner app: No-go zones, Soft zones, Anatomy, Head (from headset_manifest.json 'group';
        // older manifests without 'group' are grouped by their 'category')
        static readonly string[] PreferredOrder = { "No-go zones", "Soft zones", "Anatomy", "Head" };
        readonly List<string> groupOrder = new();
        readonly Dictionary<string, List<string>> groupItems = new();
        readonly Dictionary<string, bool> expanded = new();
        readonly Dictionary<string, string> originOf = new();
        readonly List<GameObject> pathObjects = new();
        bool showPaths = true;
        GUIStyle boldToggle;

        static Color LmColor(string n) =>
            n.Contains("inner_eye") ? Color.green : n.Contains("outer_eye") ? Color.yellow :
            n.Contains("tragus") || n.Contains("auricular") ? Color.cyan : n == "nasion" ? new Color(1f, 0.6f, 0f) : Color.red;

        void Update()
        {
            if (loader == null || !loader.IsLoaded) return;
            if (markers.Count == 0) CreateMarkers();
            if (UnityEngine.XR.XRSettings.isDeviceActive) return;      // headset on: the headset moves the camera (QuestControls)
            HandleMouse();
            var cam = Camera.main; if (cam == null) return;
            Transform root = loader.PatientRoot;
            Quaternion q = Quaternion.Euler(pitch, yaw, 0f);
            Vector3 target = root.position + panOffset;
            cam.transform.SetPositionAndRotation(target - q * Vector3.forward * distance, q);
            cam.nearClipPlane = 0.01f;
        }

        void HandleMouse()
        {
            Vector2 delta = Vector2.zero, pos = Vector2.zero; float wheel = 0f; bool left = false, right = false, down = false, up = false;
#if ENABLE_INPUT_SYSTEM
            var m = Mouse.current; if (m == null) return;
            // Unity 6 (Input System 1.8+) reports about 1 per wheel notch, older versions 120 per notch
            float raw = m.scroll.ReadValue().y; wheel = Mathf.Abs(raw) >= 10f ? raw / 120f : raw;
            delta = m.delta.ReadValue() * 0.2f; pos = m.position.ReadValue();
            left = m.leftButton.isPressed; right = m.rightButton.isPressed;
            down = m.leftButton.wasPressedThisFrame; up = m.leftButton.wasReleasedThisFrame;
#else
            delta = new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")) * 3f; wheel = Input.mouseScrollDelta.y;
            pos = Input.mousePosition; left = Input.GetMouseButton(0); right = Input.GetMouseButton(1);
            down = Input.GetMouseButtonDown(0); up = Input.GetMouseButtonUp(0);
#endif
            if (pos.x < PanelWidth + 10f) return;                       // mouse is over the panel
            if (down) pressPos = pos;
            if (up && editMode && editing != null && (pos - pressPos).magnitude < 4f) PlaceLandmark(pos);  // click, not drag
            if (left) { yaw += delta.x; pitch = Mathf.Clamp(pitch - delta.y, -85f, 85f); }
            if (right)
            {
                var cam = Camera.main.transform;
                panOffset -= (cam.right * delta.x + cam.up * delta.y) * 0.0015f * distance;
            }
            distance = Mathf.Clamp(distance * Mathf.Pow(0.85f, wheel), MinDist, MaxDist);      // 15 % per wheel notch
        }

        void CreateMarkers()
        {
            foreach (string name in loader.TouchOrder())
            {
                var s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                s.name = "landmark_" + name;
                Destroy(s.GetComponent<Collider>());
                s.transform.SetParent(loader.PatientRoot, false);
                s.transform.localPosition = loader.LandmarkLocal(name);
                s.transform.localScale = Vector3.one * 0.006f;
                var mat = PatientLoader.SolidMaterial(LmColor(name));        // default material is pink in a headset build
                if (mat != null) s.GetComponent<Renderer>().sharedMaterial = mat;
                else s.GetComponent<Renderer>().material.color = LmColor(name);
                markers.Add(s); markerByName[name] = s;
            }
            // the skin needs a collider so a mouse click can find the point on it
            if (loader.Layers.TryGetValue("scalp", out var scalp))
                foreach (var mf in scalp.GetComponentsInChildren<MeshFilter>(true))
                    if (mf.sharedMesh != null && mf.sharedMesh.isReadable && mf.GetComponent<MeshCollider>() == null)
                        mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
            foreach (JObject L in loader.Manifest["layers"]) visible[(string)L["name"]] = (bool)L["visible"];
            BuildGroups();
        }

        void BuildGroups()
        {
            var firstSeen = new Dictionary<string, int>();
            foreach (JObject L in loader.Manifest["layers"])
            {
                string n = (string)L["name"];
                string g = (string)(L["group"] ?? L["category"]) ?? "Other";
                if (!groupItems.ContainsKey(g)) { groupItems[g] = new List<string>(); groupOrder.Add(g); expanded[g] = false; firstSeen[g] = firstSeen.Count; }
                groupItems[g].Add(n);
                originOf[n] = (string)L["origin"] ?? "";
            }
            System.Func<string, int> rank = grp => { int i = System.Array.IndexOf(PreferredOrder, grp); return i >= 0 ? i : 100 + firstSeen[grp]; };
            groupOrder.Sort((a, b) => rank(a).CompareTo(rank(b)));
            // robot paths and targets from paths.glb (path_1, path_2 ..., target_<name>)
            foreach (var kv in loader.Layers)
                if (kv.Key.StartsWith("path_") || kv.Key.StartsWith("target_")) pathObjects.Add(kv.Value);
        }

        void PlaceLandmark(Vector2 screenPos)
        {
            var ray = Camera.main.ScreenPointToRay(screenPos);
            if (!Physics.Raycast(ray, out RaycastHit hit, 10f)) { simResult = "Click on the skin (scalp layer must be visible)"; return; }
            Vector3 local = loader.PatientRoot.InverseTransformPoint(hit.point);
            loader.SetLandmark(editing, local);
            markerByName[editing].transform.localPosition = local;
            simResult = $"{editing} moved and saved to headset_manifest.json";
            if (registration != null) registration.ResetCapture();
        }

        void SetAll(System.Func<JObject, bool> rule)
        {
            foreach (JObject L in loader.Manifest["layers"])
            {
                string n = (string)L["name"]; visible[n] = rule(L); loader.SetLayerVisible(n, visible[n]);
            }
        }

        static string OriginTag(string origin) =>
            origin.StartsWith("prior") ? "  [PRIOR]" : origin.StartsWith("estimate") ? "  [ESTIMATE]" :
            origin.StartsWith("patient anatomy") || origin.StartsWith("atlas") ? "  [atlas function]" : "";

        void SimulateRegistration()
        {
            if (registration == null) { simResult = "Assign 'registration' on DesktopViewer"; return; }
            // virtual head = where the real patient would be; random pose 0.5-0.7 m in front, tilted up to 25 deg
            if (virtualHead == null) virtualHead = new GameObject("VirtualHead (simulation)").transform;
            virtualHead.SetPositionAndRotation(new Vector3(Random.Range(-0.1f, 0.1f), Random.Range(-0.05f, 0.1f), Random.Range(0.5f, 0.7f)),
                Quaternion.Euler(Random.Range(-25f, 25f), Random.Range(-180f, 180f), Random.Range(-25f, 25f)));
            registration.ResetCapture();
            foreach (string lm in registration.Order)
                registration.CaptureWorld(virtualHead.TransformPoint(loader.LandmarkLocal(lm)) + Random.insideUnitSphere * 0.0025f);
            Vector3 hip = loader.RegionLocal(17);                                        // left hippocampus
            float tre = (loader.PatientRoot.TransformPoint(hip) - virtualHead.TransformPoint(hip)).magnitude * 1000f;
            simResult = $"{registration.CapturedCount} landmarks touched (noise up to 2.5 mm)\nFRE = {registration.LastFreMm:F1} mm\n" +
                        $"Target error at left hippocampus = {tre:F1} mm";
            panOffset = Vector3.zero;
            Debug.Log("Simulated registration: " + simResult.Replace("\n", "; "));
        }

        void OnGUI()
        {
            GUILayout.BeginArea(new Rect(10, 10, PanelWidth, Screen.height - 20), GUI.skin.box);
            GUILayout.Label("<b>SEEG Planner - desktop viewer</b>", new GUIStyle(GUI.skin.label) { richText = true });
            if (loader == null || !loader.IsLoaded)
            {
                GUILayout.Label("Loading patient... (check the Console if this stays)\nSet 'Package Folder' on PatientLoader.");
                GUILayout.EndArea(); return;
            }
            GUILayout.Label("Mouse: left drag = rotate, right drag = pan, wheel = zoom");
            GUILayout.BeginHorizontal();
            GUILayout.Label("Zoom", GUILayout.Width(40));
            // slider in log scale, right = closer
            float z = GUILayout.HorizontalSlider(-Mathf.Log(distance), -Mathf.Log(MaxDist), -Mathf.Log(MinDist));
            distance = Mathf.Clamp(Mathf.Exp(-z), MinDist, MaxDist);
            if (GUILayout.Button("-", GUILayout.Width(24))) distance = Mathf.Min(distance / 0.7f, MaxDist);
            if (GUILayout.Button("+", GUILayout.Width(24))) distance = Mathf.Max(distance * 0.7f, MinDist);
            if (GUILayout.Button("Reset", GUILayout.Width(50))) { distance = 0.45f; panOffset = Vector3.zero; yaw = 180f; pitch = 10f; }
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Default")) SetAll(L => (bool)L["visible"]);
            if (GUILayout.Button("All")) SetAll(L => true);
            if (GUILayout.Button("None")) SetAll(L => false);
            GUILayout.EndHorizontal();
            GUILayout.Label("Layers: tick a group to show all of it, > to choose single layers");

            if (boldToggle == null) boldToggle = new GUIStyle(GUI.skin.toggle) { richText = true };
            scroll = GUILayout.BeginScrollView(scroll, GUILayout.Height(Mathf.Max(150f, Screen.height - (editMode ? 660f : 380f))));
            foreach (string g in groupOrder)
            {
                var items = groupItems[g];
                int on = 0; foreach (string n in items) if (visible[n]) on++;
                bool all = on == items.Count;
                GUILayout.BeginHorizontal();
                if (GUILayout.Button(expanded[g] ? "v" : ">", GUILayout.Width(22))) expanded[g] = !expanded[g];
                string part = on > 0 && !all ? $"  ({on} shown)" : "";
                bool gv = GUILayout.Toggle(all, $" <b>{g}</b>  [{items.Count}]{part}", boldToggle);
                if (gv != all) foreach (string n in items) { visible[n] = gv; loader.SetLayerVisible(n, gv); }
                GUILayout.EndHorizontal();
                if (!expanded[g]) continue;
                foreach (string n in items)
                {
                    GUILayout.BeginHorizontal(); GUILayout.Space(30);
                    bool v = GUILayout.Toggle(visible[n], $" {n}{OriginTag(originOf[n])}");
                    if (v != visible[n]) { visible[n] = v; loader.SetLayerVisible(n, v); }
                    GUILayout.EndHorizontal();
                }
            }
            if (pathObjects.Count > 0)
            {
                GUILayout.BeginHorizontal(); GUILayout.Space(26);
                bool pv = GUILayout.Toggle(showPaths, " <b>Robot paths and targets</b>", boldToggle);
                if (pv != showPaths) { showPaths = pv; foreach (var o in pathObjects) o.SetActive(pv); }
                GUILayout.EndHorizontal();
            }
            GUILayout.EndScrollView();

            bool sl = GUILayout.Toggle(showLandmarks, " Show alignment landmarks");
            if (sl != showLandmarks) { showLandmarks = sl; foreach (var m in markers) m.SetActive(sl); }
            bool em = GUILayout.Toggle(editMode, " Edit landmarks (click on the skin)");
            if (em != editMode) { editMode = em; editing = null; }
            if (editMode)
            {
                foreach (string n in loader.TouchOrder())
                {
                    if (GUILayout.Toggle(editing == n, $" {n}", GUI.skin.button)) editing = n;
                }
                if (editing != null) GUILayout.Label("Now click on the skin: " + (string)loader.Manifest["landmarks"][editing]["touch_hint"]);
            }
            if (GUILayout.Button("Simulate registration (random head pose)")) SimulateRegistration();
            if (simResult != "") GUILayout.Label(simResult);
            GUILayout.EndArea();
        }
    }
}
