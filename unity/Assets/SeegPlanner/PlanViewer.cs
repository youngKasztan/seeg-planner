// PlanViewer.cs - shows the electrode plan (plan.json from planner/plan_seeg.py) inside the patient model.
// Put it on the same object as PatientLoader. plan.json must be in the same folder as headset_manifest.json.
// Each electrode = thin cylinder from the skin entry to the tip (green = no warnings, yellow = warnings)
// with white spheres at the contacts. A small panel on the right lists the electrodes.
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace SeegPlanner
{
    public class PlanViewer : MonoBehaviour
    {
        public PatientLoader loader;
        public float shaftDiameterMm = 1.2f;            // real DIXI shaft is 0.8 mm; drawn a bit thicker
        public float contactDiameterMm = 2.0f;

        JObject plan;
        string status = "";
        readonly List<(JObject e, GameObject root)> electrodes = new();
        Vector2 scroll;
        bool built;

        void Update()
        {
            if (built || loader == null || !loader.IsLoaded) return;
            built = true;
            string path = Path.Combine(Path.GetDirectoryName(loader.ManifestPath), "plan.json");
            if (!File.Exists(path)) { status = "No plan.json next to headset_manifest.json (run planner/plan_seeg.py)"; return; }
            plan = JObject.Parse(File.ReadAllText(path));
            foreach (JObject e in plan["electrodes"]) electrodes.Add((e, Build(e)));
            status = $"{electrodes.Count} electrodes";
        }

        GameObject Build(JObject e)
        {
            var root = new GameObject("electrode_" + (string)e["id"]);
            root.transform.SetParent(loader.PatientRoot, false);
            Vector3 a = PatientLoader.SceneToUnityLocal(e["entry_scene_m"]), b = PatientLoader.SceneToUnityLocal(e["tip_scene_m"]);
            Color col = (string)e["status"] == "ok" ? new Color(0.2f, 0.9f, 0.3f) : new Color(1f, 0.85f, 0.1f);

            var shaft = GameObject.CreatePrimitive(PrimitiveType.Cylinder);   // unit cylinder: height 2 along Y, radius 0.5
            Destroy(shaft.GetComponent<Collider>());
            shaft.transform.SetParent(root.transform, false);
            float len = Vector3.Distance(a, b), d = shaftDiameterMm / 1000f;
            shaft.transform.localPosition = (a + b) * 0.5f;
            shaft.transform.localRotation = Quaternion.FromToRotation(Vector3.up, (b - a).normalized);
            shaft.transform.localScale = new Vector3(d, len / 2f, d);
            shaft.GetComponent<Renderer>().material.color = col;

            foreach (var c in e["contacts_scene_m"])
            {
                var s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                Destroy(s.GetComponent<Collider>());
                s.transform.SetParent(root.transform, false);
                s.transform.localPosition = PatientLoader.SceneToUnityLocal(c);
                s.transform.localScale = Vector3.one * (contactDiameterMm / 1000f);
                s.GetComponent<Renderer>().material.color = Color.white;
            }
            return root;
        }

        void OnGUI()
        {
            if (!built) return;
            float w = 320f;
            GUILayout.BeginArea(new Rect(Screen.width - w - 10, 10, w, Mathf.Min(Screen.height - 20, 420)), GUI.skin.box);
            GUILayout.Label("<b>Electrode plan</b>  " + status, new GUIStyle(GUI.skin.label) { richText = true });
            scroll = GUILayout.BeginScrollView(scroll);
            foreach (var (e, root) in electrodes)
            {
                var targets = string.Join(" + ", e["targets"].ToObject<string[]>());
                bool on = GUILayout.Toggle(root.activeSelf, $" {(string)e["id"]}: {targets}");
                if (on != root.activeSelf) root.SetActive(on);
                var vd = e["min_distance_mm"]["vessels"];
                GUILayout.Label($"   {(string)e["electrode"]}, {(float)e["length_mm"]:F0} mm, angle {(float)e["angle_deg"]:F0} deg, " +
                                $"vessels {(vd == null || vd.Type == JTokenType.Null ? "not imaged" : ((float)vd).ToString("F1") + " mm")}");
                foreach (var wtok in e["warnings"]) GUILayout.Label("   ! " + (string)wtok);
            }
            GUILayout.EndScrollView();
            if (plan != null) GUILayout.Label((string)plan["note"]);
            GUILayout.EndArea();
        }
    }
}
