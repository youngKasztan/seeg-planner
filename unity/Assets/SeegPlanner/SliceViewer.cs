// SliceViewer.cs - MRI slice mode: one T1 slice (axial, coronal or sagittal) shown inside the hologram, exactly where
// it lies in the head, scrolled through the head by moving the right hand with the grip held.
//
// Data: mri_volume.bytes + mri_volume.json in the patient package (written by the planner's "Export to headset",
// path_planner/mri_volume.py): uint8 voxels on a 1 mm grid aligned with PatientRoot's axes,
//   i -> +x (patient left), j -> +y (superior), k -> +z (posterior), x fastest; 0 = outside the head (transparent).
// The slice is a world-space uGUI RawImage (UI/Default survives a player build) parented to PatientRoot, so it moves
// with the hologram (registration, head-marker tracking, carrying by hand).
//
// Planes and textures (texture u right, v up):
//   Axial    (constant j): u = i (left), v = k (posterior)      plane spans PatientRoot x and z
//   Coronal  (constant k): u = i (left), v = j (superior)      plane spans x and y
//   Sagittal (constant i): u = k (posterior), v = j (superior) plane spans z and y
// The thumbnails on the Layers & paths panel use the same textures (axial shown with anterior up).
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace SeegPlanner
{
    public class SliceViewer : MonoBehaviour
    {
        public enum Plane { Off = -1, Axial = 0, Coronal = 1, Sagittal = 2 }

        public PatientLoader loader;
        [Tooltip("Opacity of the slice inside the hologram (0-1); outside the head it is always transparent")]
        [Range(0.1f, 1f)] public float opacity = 0.85f;

        public Plane Mode { get; private set; } = Plane.Off;
        public bool Available => vol != null;
        public bool Scrolling { get; private set; }
        public string LoadMessage { get; private set; } = "MRI not loaded";

        byte[] vol; int nx, ny, nz; float s; Vector3 origin;
        readonly int[] index = new int[3];                  // current slice per plane (axial j, coronal k, sagittal i)
        readonly Texture2D[] tex = new Texture2D[3];
        readonly Color32[][] pix = new Color32[3][];
        RectTransform canvasRt; RawImage image;
        Vector3 scrollStart; int scrollStartIndex; bool prevGrip;

        // ---------------------------------------------------------------- loading

        /// Reads mri_volume.json / .bytes next to headset_manifest.json. Safe to call more than once.
        public void Load()
        {
            if (vol != null || loader == null || !loader.IsLoaded) return;
            string dir = Path.GetDirectoryName(loader.ManifestPath) ?? "";
            string jp = Path.Combine(dir, "mri_volume.json"), bp = Path.Combine(dir, "mri_volume.bytes");
            if (!File.Exists(jp) || !File.Exists(bp))
            {
                LoadMessage = "no MRI in the patient package - press 'Export to headset' in the planner";
                return;
            }
            try
            {
                var meta = JObject.Parse(File.ReadAllText(jp));
                nx = (int)meta["dims"][0]; ny = (int)meta["dims"][1]; nz = (int)meta["dims"][2];
                s = (float)meta["spacing_m"];
                origin = new Vector3((float)meta["origin_local_m"][0], (float)meta["origin_local_m"][1], (float)meta["origin_local_m"][2]);
                var bytes = File.ReadAllBytes(bp);
                if (bytes.Length != nx * ny * nz) { LoadMessage = $"mri_volume.bytes has {bytes.Length} bytes, expected {nx * ny * nz}"; return; }
                vol = bytes;
            }
            catch (System.Exception e) { LoadMessage = "MRI load error: " + e.Message; Debug.LogException(e); return; }

            index[(int)Plane.Axial] = ny / 2; index[(int)Plane.Coronal] = nz / 2; index[(int)Plane.Sagittal] = nx / 2;
            for (int p = 0; p < 3; p++)
            {
                Size((Plane)p, out int w, out int h);
                tex[p] = new Texture2D(w, h, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear, wrapMode = TextureWrapMode.Clamp };
                pix[p] = new Color32[w * h];
                Fill((Plane)p);
            }
            BuildSliceObject();
            LoadMessage = $"MRI {nx} x {ny} x {nz} voxels, {s * 1000f:F1} mm";
            Debug.Log("[SliceViewer] " + LoadMessage);
        }

        void Size(Plane p, out int w, out int h)
        {
            switch (p)
            {
                case Plane.Axial: w = nx; h = nz; break;
                case Plane.Coronal: w = nx; h = ny; break;
                default: w = nz; h = ny; break;
            }
        }

        public int Count(Plane p) => p == Plane.Axial ? ny : p == Plane.Coronal ? nz : nx;
        public int Index(Plane p) => p == Plane.Off ? 0 : index[(int)p];
        public Texture2D Texture(Plane p) => p == Plane.Off ? null : tex[(int)p];

        /// Copies one slice of the volume into the plane's texture (opaque inside the head, transparent outside).
        void Fill(Plane p)
        {
            int pi = (int)p, n = index[pi];
            var px = pix[pi];
            byte a = (byte)Mathf.RoundToInt(255f * opacity);
            int w = tex[pi].width, h = tex[pi].height;
            for (int v = 0; v < h; v++)
                for (int u = 0; u < w; u++)
                {
                    int i, j, k;
                    switch (p)
                    {
                        case Plane.Axial: i = u; j = n; k = v; break;
                        case Plane.Coronal: i = u; j = v; k = n; break;
                        default: i = n; j = v; k = u; break;
                    }
                    byte g = vol[(k * ny + j) * nx + i];
                    px[v * w + u] = new Color32(g, g, g, g == 0 ? (byte)0 : a);
                }
            tex[pi].SetPixels32(px);
            tex[pi].Apply(false);
        }

        // ---------------------------------------------------------------- the slice in the hologram

        void BuildSliceObject()
        {
            var go = new GameObject("MriSlice");
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvas.sortingOrder = 10;
            canvasRt = go.GetComponent<RectTransform>();
            canvasRt.pivot = Vector2.zero;
            canvasRt.SetParent(loader.PatientRoot, false);
            image = new GameObject("Image").AddComponent<RawImage>();
            image.transform.SetParent(go.transform, false);
            var r = image.rectTransform;
            r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one; r.offsetMin = Vector2.zero; r.offsetMax = Vector2.zero;
            image.raycastTarget = false;
            go.SetActive(false);
        }

        /// Off, or show the given plane in the hologram.
        public void SetMode(Plane p)
        {
            if (!Available) p = Plane.Off;
            Mode = p;
            Scrolling = false;
            if (canvasRt == null) return;
            canvasRt.gameObject.SetActive(p != Plane.Off);
            if (p != Plane.Off) Place();
        }

        /// Puts the slice canvas at its place in PatientRoot (1 canvas unit = 1 voxel).
        void Place()
        {
            var p = Mode; int n = index[(int)p];
            Size(p, out int w, out int h);
            canvasRt.sizeDelta = new Vector2(w, h);
            canvasRt.localScale = Vector3.one * s;
            float half = s * 0.5f;                                  // texel centres sit on the voxel centres
            switch (p)
            {
                case Plane.Axial:      // canvas X = +x, Y = +z
                    canvasRt.localRotation = Quaternion.LookRotation(Vector3.down, Vector3.forward);
                    canvasRt.localPosition = new Vector3(origin.x - half, origin.y + n * s, origin.z - half);
                    break;
                case Plane.Coronal:    // canvas X = +x, Y = +y
                    canvasRt.localRotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
                    canvasRt.localPosition = new Vector3(origin.x - half, origin.y - half, origin.z + n * s);
                    break;
                default:               // sagittal: canvas X = +z, Y = +y
                    canvasRt.localRotation = Quaternion.LookRotation(Vector3.left, Vector3.up);
                    canvasRt.localPosition = new Vector3(origin.x + n * s, origin.y - half, origin.z - half);
                    break;
            }
            image.texture = tex[(int)p];
        }

        Vector3 NormalLocal(Plane p) => p == Plane.Axial ? Vector3.up : p == Plane.Coronal ? Vector3.forward : Vector3.right;

        /// Sets the slice of plane p (clamped). Updates the texture (and the hologram if p is shown).
        public void SetIndex(Plane p, int n)
        {
            if (!Available || p == Plane.Off) return;
            n = Mathf.Clamp(n, 0, Count(p) - 1);
            if (n == index[(int)p]) return;
            index[(int)p] = n;
            Fill(p);
            if (p == Mode) Place();
        }

        // ---------------------------------------------------------------- scrolling with the right hand

        /// Every frame from QuestControls. Grip pressed (when allowed to start, i.e. not on the panel) starts scrolling;
        /// while it is held, moving the hand along the slice normal moves the slice by the same distance.
        public void UpdateScroll(bool gripHeld, bool allowStart, Vector3 handWorld)
        {
            if (Mode == Plane.Off || loader == null || loader.PatientRoot == null) { Scrolling = false; prevGrip = gripHeld; return; }
            if (gripHeld && !prevGrip && allowStart)
            {
                Scrolling = true; scrollStart = handWorld; scrollStartIndex = index[(int)Mode];
            }
            if (!gripHeld) Scrolling = false;
            if (Scrolling)
            {
                var root = loader.PatientRoot;
                Vector3 nWorld = root.TransformDirection(NormalLocal(Mode));
                float voxelWorld = s * root.lossyScale.x;
                float d = Vector3.Dot(handWorld - scrollStart, nWorld.normalized);
                SetIndex(Mode, scrollStartIndex + Mathf.RoundToInt(d / Mathf.Max(voxelWorld, 1e-6f)));
            }
            prevGrip = gripHeld;
        }

        /// e.g. "Axial 120 / 215 (+12 mm)" - position relative to the head centre along the plane normal.
        public string Describe(Plane p)
        {
            if (!Available || p == Plane.Off) return "";
            int n = index[(int)p];
            float local = p == Plane.Axial ? origin.y + n * s : p == Plane.Coronal ? origin.z + n * s : origin.x + n * s;
            string dir = p == Plane.Axial ? (local >= 0 ? "sup" : "inf") : p == Plane.Coronal ? (local >= 0 ? "post" : "ant") : (local >= 0 ? "left" : "right");
            return $"{p} {n + 1}/{Count(p)} ({Mathf.Abs(local) * 1000f:F0} mm {dir})";
        }
    }
}
