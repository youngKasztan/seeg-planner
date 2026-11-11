// LayerPanel.cs - floating "Layers & paths" panel on the Quest: switch brain layers and robot paths on / off.
//
// Layers and groups are the same as in the planner app (headset_manifest.json "layers": name, group, colour,
// visible), paths come from plan.json ("paths": id, targets, colour). Created by QuestControls.
//
//   Right thumbstick click : show / hide the panel (it appears in front of you, slightly to the right)
//   Point the right controller at the panel : a laser shows where you point, the row under it is highlighted
//   Right trigger on a row : layer / path on or off;  on a group title : the whole group on or off
//   Right grip while pointing at the panel : drag the panel (it keeps facing you); release = it stays there
//
// While the laser is on the panel the right trigger clicks the panel and does NOT record a landmark.
// The panel is a world-space uGUI canvas (UI/Default + the built-in font survive a player build); clicks are found
// by intersecting the controller ray with the canvas plane, so no EventSystem / XR Interaction Toolkit is needed.
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace SeegPlanner
{
    public class LayerPanel : MonoBehaviour
    {
        public PatientLoader loader;
        [Tooltip("Width of the panel in metres")]
        public float panelWidth = 0.42f;
        [Tooltip("The laser reaches this far (metres)")]
        public float maxRayLength = 3f;

        public bool Visible => root != null && root.gameObject.activeSelf;
        /// True while the right controller points at the panel (QuestControls then gives the trigger to the panel).
        public bool Hovering { get; private set; }

        // layout in canvas pixels (x right, y down from the top-left corner)
        const float ColW = 340f, RowH = 36f, Pad = 10f, TitleH = 54f, Swatch = 22f;
        float W, H;

        enum Kind { Layer, Group, Path, Targets, AllPathsOn, AllPathsOff }
        class Row
        {
            public Kind kind;
            public string key;                  // layer name / group name / path id
            public List<string> nodes = new();  // nodes switched by this row (paths: all parts of the path)
            public string text;                 // label (paths)
            public Rect rect;                   // top-left pixel rect on the canvas
            public Image bg, swatch; public Text label;
            public Color colour;
        }
        readonly List<Row> rows = new();
        readonly Dictionary<string, List<string>> groupLayers = new();

        RectTransform root;
        Font font;
        Transform laser, dot;
        Row hover;
        bool dragging; Vector3 dragLocal; float dragDistance;
        bool placedOnce;

        static readonly Color RowBg = new Color(0.12f, 0.12f, 0.14f, 0.92f);
        static readonly Color RowHover = new Color(0.25f, 0.35f, 0.55f, 0.95f);
        static readonly Color GroupBg = new Color(0.2f, 0.2f, 0.24f, 0.95f);
        static readonly Color OffSwatch = new Color(0.25f, 0.25f, 0.25f, 1f);
        static readonly Color OffText = new Color(0.55f, 0.55f, 0.55f, 1f);

        // ---------------------------------------------------------------- build

        /// Builds the panel from the manifest and plan.json (call once the patient is loaded).
        public void Build()
        {
            if (root != null || loader == null || !loader.IsLoaded) return;
            font = BuiltinFont();

            // groups in the order they appear in the manifest (= planner app order)
            var groups = new List<string>();
            var layerInfo = new Dictionary<string, JObject>();
            foreach (JObject L in loader.Manifest["layers"])
            {
                string name = (string)L["name"], g = (string)L["group"] ?? "Other";
                if (!loader.Layers.ContainsKey((string)L["node"] ?? name) && !loader.Layers.ContainsKey(name)) continue;
                if (!groupLayers.ContainsKey(g)) { groupLayers[g] = new List<string>(); groups.Add(g); }
                groupLayers[g].Add(name);
                layerInfo[name] = L;
            }

            // two columns, each group goes to the shorter column
            var colRows = new[] { 0, 0 };
            var colOfGroup = new Dictionary<string, int>();
            foreach (var g in groups)
            {
                int c = colRows[0] <= colRows[1] ? 0 : 1;
                colOfGroup[g] = c; colRows[c] += 1 + groupLayers[g].Count;
            }
            var paths = ReadPaths();
            int pathRows = (paths.Count + 1) / 2;
            W = 2 * ColW + 3 * Pad;
            float layersH = Mathf.Max(colRows[0], colRows[1]) * RowH;
            float pathsTop = TitleH + layersH + Pad;
            H = pathsTop + RowH + pathRows * RowH + Pad;

            var go = new GameObject("LayerPanel");
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvas.sortingOrder = 90;
            root = go.GetComponent<RectTransform>();
            root.sizeDelta = new Vector2(W, H);
            root.pivot = new Vector2(0.5f, 0.5f);
            go.transform.localScale = Vector3.one * (panelWidth / W);

            var bg = MakeImage(root, new Rect(0, 0, W, H), new Color(0f, 0f, 0f, 0.8f));
            bg.name = "Background";
            MakeText(root, new Rect(Pad, 6, W - 2 * Pad, 26), "<b>Layers & paths</b>", 24, TextAnchor.MiddleLeft, Color.white);
            MakeText(root, new Rect(Pad, 30, W - 2 * Pad, 20),
                     "point + right trigger = on/off (group title = whole group)    right grip = move    right stick click = hide",
                     15, TextAnchor.MiddleLeft, new Color(0.75f, 0.75f, 0.75f));

            // layer columns
            var y = new[] { TitleH, TitleH };
            foreach (var g in groups)
            {
                int c = colOfGroup[g];
                float x = Pad + c * (ColW + Pad);
                AddRow(new Row { kind = Kind.Group, key = g, rect = new Rect(x, y[c], ColW, RowH - 4) }, GroupLabel(g), Color.white);
                y[c] += RowH;
                foreach (var name in groupLayers[g])
                {
                    var L = layerInfo[name];
                    var col = L["colour"] != null ? new Color((float)L["colour"][0], (float)L["colour"][1], (float)L["colour"][2], 1f) : Color.gray;
                    var r = new Row { kind = Kind.Layer, key = name, colour = col, rect = new Rect(x + 12, y[c], ColW - 12, RowH - 4) };
                    r.nodes.Add((string)L["node"] ?? name);
                    AddRow(r, Pretty(name), col);
                    y[c] += RowH;
                }
            }

            // robot paths
            float bw = (W - 2 * Pad - 3 * 8f) / 4f;
            MakeText(root, new Rect(Pad, pathsTop, bw, RowH - 4), "<b>Robot paths</b>", 20, TextAnchor.MiddleLeft, Color.white);
            var targets = new Row { kind = Kind.Targets, key = "targets", colour = new Color(1f, 0.1f, 0.9f), rect = new Rect(Pad + (bw + 8f), pathsTop, bw, RowH - 4) };
            foreach (var n in loader.Layers.Keys) if (n.StartsWith("target_")) targets.nodes.Add(n);
            AddRow(targets, "Targets", targets.colour);
            AddRow(new Row { kind = Kind.AllPathsOn, key = "all_on", rect = new Rect(Pad + 2 * (bw + 8f), pathsTop, bw, RowH - 4) }, "All paths on", Color.white);
            AddRow(new Row { kind = Kind.AllPathsOff, key = "all_off", rect = new Rect(Pad + 3 * (bw + 8f), pathsTop, bw, RowH - 4) }, "All paths off", Color.white);
            for (int i = 0; i < paths.Count; i++)
            {
                var p = paths[i];
                float x = Pad + (i % 2) * (ColW + Pad), py = pathsTop + RowH + (i / 2) * RowH;
                p.rect = new Rect(x, py, ColW, RowH - 4);
                AddRow(p, p.text, p.colour);
            }
            if (paths.Count == 0)
                MakeText(root, new Rect(Pad, pathsTop + RowH, W - 2 * Pad, RowH - 4), "no paths in plan.json", 18, TextAnchor.MiddleLeft, OffText);

            laser = MakeBar("LayerPanelLaser", new Color(0.4f, 0.9f, 1f));
            dot = MakeDot("LayerPanelDot", new Color(0.4f, 0.9f, 1f));
            root.gameObject.SetActive(false);
            Refresh();
        }

        /// Paths from plan.json; each row switches every node of the path (path_1, path_1_straight, path_1_arc1 ...).
        List<Row> ReadPaths()
        {
            var list = new List<Row>();
            string dir = Path.GetDirectoryName(loader.ManifestPath);
            string planPath = Path.Combine(dir ?? "", "plan.json");
            if (!File.Exists(planPath)) return list;
            JObject plan;
            try { plan = JObject.Parse(File.ReadAllText(planPath)); } catch { return list; }
            if (plan["paths"] == null) return list;
            foreach (JObject p in plan["paths"])
            {
                string id = (string)p["id"];
                var r = new Row { kind = Kind.Path, key = id };
                foreach (var n in loader.Layers.Keys)
                    if (n == id || n.StartsWith(id + "_")) r.nodes.Add(n);
                if (r.nodes.Count == 0) continue;
                var c = p["colour"];
                r.colour = c != null ? new Color((float)c[0], (float)c[1], (float)c[2], 1f) : new Color(0.2f, 0.8f, 1f);
                var tg = new List<string>();
                if (p["targets"] != null) foreach (var t in p["targets"]) tg.Add((string)t);
                string extra = p["length_mm"] != null ? $"  {(float)p["length_mm"]:F0} mm" : "";
                r.text = Pretty(id) + (tg.Count > 0 ? "  -> " + string.Join(", ", tg) : "") + extra;
                list.Add(r);
            }
            return list;
        }

        void AddRow(Row r, string label, Color swatchColour)
        {
            r.bg = MakeImage(root, r.rect, r.kind == Kind.Group ? GroupBg : RowBg);
            bool hasSwatch = r.kind == Kind.Layer || r.kind == Kind.Path || r.kind == Kind.Targets;
            float tx = 8f;
            if (hasSwatch)
            {
                r.swatch = MakeImage(root, new Rect(r.rect.x + 8f, r.rect.y + (r.rect.height - Swatch) / 2f, Swatch, Swatch), swatchColour);
                tx = 8f + Swatch + 8f;
            }
            r.label = MakeText(root, new Rect(r.rect.x + tx, r.rect.y, r.rect.width - tx - 4f, r.rect.height), label,
                               r.kind == Kind.Group ? 20 : 19, r.kind == Kind.AllPathsOn || r.kind == Kind.AllPathsOff ? TextAnchor.MiddleCenter : TextAnchor.MiddleLeft,
                               Color.white);
            if (r.kind == Kind.Group) r.label.fontStyle = FontStyle.Bold;
            rows.Add(r);
        }

        // ---------------------------------------------------------------- show / hide / pointer

        /// Show / hide. The first time (and whenever it is shown again far away) it is placed in front of the user.
        public void Toggle(Transform cam)
        {
            if (root == null) Build();
            if (root == null) return;
            bool show = !root.gameObject.activeSelf;
            root.gameObject.SetActive(show);
            if (show && (!placedOnce || (root.position - cam.position).magnitude > 2.5f)) PlaceInFront(cam);
            if (!show) { Hovering = false; hover = null; laser.gameObject.SetActive(false); dot.gameObject.SetActive(false); }
            Refresh();
        }

        void PlaceInFront(Transform cam)
        {
            Vector3 f = cam.forward; f.y = 0f; if (f.sqrMagnitude < 1e-4f) f = Vector3.forward; f.Normalize();
            Vector3 right = Vector3.Cross(Vector3.up, f);
            root.position = cam.position + f * 0.65f + right * 0.25f - Vector3.up * 0.1f;
            FaceCamera(cam);
            placedOnce = true;
        }

        void FaceCamera(Transform cam) =>
            root.rotation = Quaternion.LookRotation(root.position - cam.position, Vector3.up);   // readable side to the user

        /// Every frame from QuestControls with the right controller pose; gripHeld = right grip is down.
        public void UpdatePointer(bool ok, Vector3 origin, Quaternion rot, bool gripHeld, Transform cam)
        {
            Hovering = false; hover = null;
            if (root == null || !root.gameObject.activeSelf || !ok)
            {
                dragging = false; prevGrip = gripHeld;
                if (laser != null) { laser.gameObject.SetActive(false); dot.gameObject.SetActive(false); }
                Refresh();
                return;
            }
            Vector3 dir = rot * Vector3.forward;

            if (dragging)
            {
                if (!gripHeld) dragging = false;
                else
                {
                    root.position = origin + dir * dragDistance + rot * dragLocal;
                    FaceCamera(cam);
                }
            }

            bool hit = RayHit(origin, dir, out Vector3 point, out Vector2 px);
            if (hit)
            {
                Hovering = true;
                foreach (var r in rows) if (r.rect.Contains(px)) { hover = r; break; }
                if (gripHeld && !dragging && !prevGrip)               // start dragging
                {
                    dragging = true;
                    dragDistance = Vector3.Dot(point - origin, dir);
                    dragLocal = Quaternion.Inverse(rot) * (root.position - (origin + dir * dragDistance));
                }
                ShowLaser(origin, point);
            }
            else if (dragging) ShowLaser(origin, origin + dir * dragDistance);
            else { laser.gameObject.SetActive(false); dot.gameObject.SetActive(false); }
            if (dragging) Hovering = true;
            prevGrip = gripHeld;
            Refresh();
        }
        bool prevGrip;

        bool RayHit(Vector3 origin, Vector3 dir, out Vector3 point, out Vector2 px)
        {
            point = default; px = default;
            Vector3 n = root.forward;
            float denom = Vector3.Dot(dir, n);
            if (Mathf.Abs(denom) < 1e-4f) return false;
            float t = Vector3.Dot(root.position - origin, n) / denom;
            if (t <= 0f || t > maxRayLength) return false;
            point = origin + dir * t;
            Vector3 local = root.InverseTransformPoint(point);          // canvas units (pixels), origin at the centre
            px = new Vector2(local.x + W / 2f, H / 2f - local.y);
            return px.x >= 0 && px.x <= W && px.y >= 0 && px.y <= H;
        }

        /// Right trigger: click the row under the laser. Returns true if the panel used the click.
        public bool Click()
        {
            if (!Hovering) return false;
            if (hover == null) return true;                              // on the panel but not on a row: swallow it
            switch (hover.kind)
            {
                case Kind.Layer:
                case Kind.Path:
                case Kind.Targets:
                    bool on = !AnyOn(hover.nodes);
                    foreach (var n in hover.nodes) loader.SetLayerVisible(n, on);
                    break;
                case Kind.Group:
                    var nodes = new List<string>();
                    foreach (var r in rows) if (r.kind == Kind.Layer && groupLayers[hover.key].Contains(r.key)) nodes.AddRange(r.nodes);
                    bool any = AnyOn(nodes);
                    foreach (var n in nodes) loader.SetLayerVisible(n, !any);
                    break;
                case Kind.AllPathsOn:
                case Kind.AllPathsOff:
                    foreach (var r in rows)
                        if (r.kind == Kind.Path) foreach (var n in r.nodes) loader.SetLayerVisible(n, hover.kind == Kind.AllPathsOn);
                    break;
            }
            Refresh();
            return true;
        }

        bool AnyOn(List<string> nodes)
        {
            foreach (var n in nodes) if (loader.Layers.TryGetValue(n, out var go) && go.activeSelf) return true;
            return false;
        }

        /// Colours of all rows from the real state of the layers (so X = skin on/off etc. is shown correctly).
        void Refresh()
        {
            if (root == null || !root.gameObject.activeSelf) return;
            foreach (var r in rows)
            {
                bool on = r.kind == Kind.Group ? GroupOn(r.key) : r.nodes.Count == 0 || AnyOn(r.nodes);
                if (r.kind == Kind.AllPathsOn || r.kind == Kind.AllPathsOff) on = true;
                r.bg.color = r == hover ? RowHover : (r.kind == Kind.Group ? GroupBg : RowBg);
                if (r.swatch != null) r.swatch.color = on ? r.colour : OffSwatch;
                r.label.color = on ? Color.white : OffText;
            }
        }

        bool GroupOn(string g)
        {
            foreach (var r in rows) if (r.kind == Kind.Layer && groupLayers[g].Contains(r.key) && AnyOn(r.nodes)) return true;
            return false;
        }

        void ShowLaser(Vector3 from, Vector3 to)
        {
            laser.gameObject.SetActive(true); dot.gameObject.SetActive(true);
            Vector3 d = to - from; float len = d.magnitude;
            if (len < 1e-4f) { laser.gameObject.SetActive(false); return; }
            laser.position = from + d * 0.5f;
            laser.rotation = Quaternion.LookRotation(d / len);
            laser.localScale = new Vector3(0.0015f, 0.0015f, len);
            dot.position = to;
        }

        // ---------------------------------------------------------------- small UI helpers

        static readonly Dictionary<string, string> Names = new()
        {
            { "csf", "CSF" }, { "skull_t1", "Skull (T1)" }, { "hypothalamus_optic_chiasm", "Hypothalamus / optic chiasm" },
        };

        static string Pretty(string name)
        {
            if (Names.TryGetValue(name, out var nice)) return nice;
            string s = name.Replace('_', ' ');
            return s.Length > 0 ? char.ToUpper(s[0]) + s.Substring(1) : s;
        }

        static string GroupLabel(string g) => g;

        static Font BuiltinFont()
        {
            Font f = null;
            try { f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
            if (f == null) try { f = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { }
            return f;
        }

        /// Places a UI element by a top-left pixel rect on the canvas.
        static void Place(RectTransform rt, Rect r)
        {
            rt.anchorMin = rt.anchorMax = new Vector2(0f, 1f);
            rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(r.x, -r.y);
            rt.sizeDelta = new Vector2(r.width, r.height);
        }

        Image MakeImage(RectTransform parent, Rect r, Color c)
        {
            var img = new GameObject("Image").AddComponent<Image>();
            img.transform.SetParent(parent, false);
            Place(img.rectTransform, r);
            img.color = c;
            img.raycastTarget = false;
            return img;
        }

        Text MakeText(RectTransform parent, Rect r, string s, int size, TextAnchor anchor, Color c)
        {
            var t = new GameObject("Text").AddComponent<Text>();
            t.transform.SetParent(parent, false);
            Place(t.rectTransform, r);
            t.font = font; t.fontSize = size; t.supportRichText = true; t.alignment = anchor; t.color = c;
            t.horizontalOverflow = HorizontalWrapMode.Overflow; t.verticalOverflow = VerticalWrapMode.Overflow;
            t.raycastTarget = false;
            t.text = s;
            return t;
        }

        static Transform MakeBar(string name, Color c)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Cube);
            g.name = name; Destroy(g.GetComponent<Collider>());
            var mat = PatientLoader.SolidMaterial(c);
            if (mat != null) g.GetComponent<Renderer>().sharedMaterial = mat;
            g.SetActive(false);
            return g.transform;
        }

        static Transform MakeDot(string name, Color c)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            g.name = name; Destroy(g.GetComponent<Collider>());
            g.transform.localScale = Vector3.one * 0.008f;
            var mat = PatientLoader.SolidMaterial(c);
            if (mat != null) g.GetComponent<Renderer>().sharedMaterial = mat;
            g.SetActive(false);
            return g.transform;
        }
    }
}
