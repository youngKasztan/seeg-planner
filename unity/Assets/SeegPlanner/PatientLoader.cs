// PatientLoader.cs - loads the patient package exported by tools/export_headset.py
// (patient_scene.glb + headset_manifest.json) and sets layer visibility/opacity.
// Requires packages: com.unity.cloud.gltfast, com.unity.nuget.newtonsoft-json.
// STATUS: written against the glTFast 6.x API; desktop test via DesktopViewer.cs (no headset needed).
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using GLTFast;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace SeegPlanner
{
    public class PatientLoader : MonoBehaviour
    {
        [Tooltip("Folder with patient_scene.glb and headset_manifest.json. Empty = Application.persistentDataPath/patient")]
        public string packageFolder = "";
        public bool useLiteScene = false;

        public Transform PatientRoot { get; private set; }          // move this to align the brain with the head
        public JObject Manifest { get; private set; }
        public readonly Dictionary<string, GameObject> Layers = new();
        public bool IsLoaded { get; private set; }
        public string ManifestPath { get; private set; }

        async void Start() { await Load(); }

        public async Task Load()
        {
            string dir = string.IsNullOrEmpty(packageFolder) ? Path.Combine(Application.persistentDataPath, "patient") : packageFolder;
            string manifestPath = ManifestPath = Path.Combine(dir, "headset_manifest.json");
            if (!File.Exists(manifestPath)) { Debug.LogError("headset_manifest.json not found in " + dir + " - set 'Package Folder' on PatientLoader"); return; }
            Manifest = JObject.Parse(File.ReadAllText(manifestPath));

            PatientRoot = new GameObject("PatientRoot").transform;
            PatientRoot.SetParent(transform, false);
            // start 0.6 m in front of the user until registration places it on the head
            PatientRoot.localPosition = new Vector3(0, 0, 0.6f);

            var gltf = new GltfImport();
            string file = Path.Combine(dir, useLiteScene ? "patient_scene_lite.glb" : "patient_scene.glb");
            if (!await gltf.Load(new System.Uri(file).AbsoluteUri)) { Debug.LogError("Could not load " + file); return; }
            await gltf.InstantiateMainSceneAsync(PatientRoot);

            // robot paths from the desktop planner (path_planner/app.py -> Export to headset), same coordinates
            string paths = Path.Combine(dir, "paths.glb");
            if (File.Exists(paths))
            {
                var g2 = new GltfImport();
                if (await g2.Load(new System.Uri(paths).AbsoluteUri)) { await g2.InstantiateMainSceneAsync(PatientRoot); Debug.Log("Robot paths loaded"); }
                else Debug.LogWarning("Could not load " + paths);
            }

            foreach (Transform t in PatientRoot.GetComponentsInChildren<Transform>(true))
                if (t != PatientRoot) Layers[t.name] = t.gameObject;

            foreach (JObject layer in Manifest["layers"])
            {
                string name = (string)layer["name"];
                SetLayerVisible(name, (bool)layer["visible"]);
            }
            IsLoaded = true;
            Debug.Log($"Patient loaded: {Layers.Count} nodes from {dir}");
        }

        public void SetLayerVisible(string name, bool visible)
        {
            if (Layers.TryGetValue(name, out var go)) go.SetActive(visible);
        }

        /// glTF scene metres -> Unity local position under PatientRoot (glTFast mirrors the X axis).
        public static Vector3 SceneToUnityLocal(JToken xyz) =>
            new Vector3(-(float)xyz[0], (float)xyz[1], (float)xyz[2]);

        public bool HasLandmark(string name) => Manifest?["landmarks"]?[name] != null;

        public Vector3 LandmarkLocal(string name)
        {
            if (!HasLandmark(name)) { Debug.LogError($"Landmark '{name}' is not in headset_manifest.json"); return Vector3.zero; }
            return SceneToUnityLocal(Manifest["landmarks"][name]["scene_m"]);
        }

        /// Landmark names in the order they are touched (from the manifest; older exports: landmark keys).
        public List<string> TouchOrder()
        {
            var order = new List<string>();
            if (Manifest["touch_order"] != null) { foreach (var t in Manifest["touch_order"]) if (HasLandmark((string)t)) order.Add((string)t); }
            else foreach (var p in ((JObject)Manifest["landmarks"]).Properties()) order.Add(p.Name);
            return order;
        }

        /// Move a landmark (PatientRoot local position, e.g. picked on the scalp) and save it to headset_manifest.json.
        public void SetLandmark(string name, Vector3 local)
        {
            var s = new[] { -local.x, local.y, local.z };                       // Unity local -> glTF scene metres
            var c = Manifest["coordinate_system"]["head_centre_ras_mm"];
            // inverse of p_scene = R (p_ras - c) / 1000 with R = [[1,0,0],[0,0,1],[0,-1,0]]
            var ras = new[] { (float)c[0] + 1000f * s[0], (float)c[1] - 1000f * s[2], (float)c[2] + 1000f * s[1] };
            var lm = (JObject)Manifest["landmarks"][name];
            lm["scene_m"] = new JArray(System.Math.Round(s[0], 5), System.Math.Round(s[1], 5), System.Math.Round(s[2], 5));
            lm["ras_mm"] = new JArray(System.Math.Round(ras[0], 2), System.Math.Round(ras[1], 2), System.Math.Round(ras[2], 2));
            lm["status"] = "set manually on the model";
            File.WriteAllText(ManifestPath, Manifest.ToString());
        }

        /// Centre of an atlas region (FreeSurfer label, e.g. 17 = left hippocampus) in PatientRoot local space.
        public Vector3 RegionLocal(int label) => SceneToUnityLocal(Manifest["region_centroids_scene_m"][label.ToString()]);
    }
}
