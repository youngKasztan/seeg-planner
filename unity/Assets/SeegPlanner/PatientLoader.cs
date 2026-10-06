// PatientLoader.cs - loads the patient package exported by tools/export_headset.py
// (patient_scene.glb + headset_manifest.json) and sets layer visibility/opacity.
// Requires packages: com.unity.cloud.gltfast, com.unity.nuget.newtonsoft-json.
// STATUS: written against the glTFast 6.x API, not yet compiled in a Unity project.
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

        async void Start() { await Load(); }

        public async Task Load()
        {
            string dir = string.IsNullOrEmpty(packageFolder) ? Path.Combine(Application.persistentDataPath, "patient") : packageFolder;
            Manifest = JObject.Parse(File.ReadAllText(Path.Combine(dir, "headset_manifest.json")));

            PatientRoot = new GameObject("PatientRoot").transform;
            PatientRoot.SetParent(transform, false);
            // start 0.6 m in front of the user until registration places it on the head
            PatientRoot.localPosition = new Vector3(0, 0, 0.6f);

            var gltf = new GltfImport();
            string file = Path.Combine(dir, useLiteScene ? "patient_scene_lite.glb" : "patient_scene.glb");
            if (!await gltf.Load("file://" + file)) { Debug.LogError("Could not load " + file); return; }
            await gltf.InstantiateMainSceneAsync(PatientRoot);

            foreach (Transform t in PatientRoot.GetComponentsInChildren<Transform>(true))
                if (t != PatientRoot) Layers[t.name] = t.gameObject;

            foreach (JObject layer in Manifest["layers"])
            {
                string name = (string)layer["name"];
                SetLayerVisible(name, (bool)layer["visible"]);
            }
            Debug.Log($"Patient loaded: {Layers.Count} nodes");
        }

        public void SetLayerVisible(string name, bool visible)
        {
            if (Layers.TryGetValue(name, out var go)) go.SetActive(visible);
        }

        /// glTF scene metres -> Unity local position under PatientRoot (glTFast mirrors the X axis).
        public static Vector3 SceneToUnityLocal(JToken xyz) =>
            new Vector3(-(float)xyz[0], (float)xyz[1], (float)xyz[2]);

        public Vector3 LandmarkLocal(string name) => SceneToUnityLocal(Manifest["landmarks"][name]["scene_m"]);
    }
}
