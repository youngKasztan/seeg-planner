// LandmarkRegistration.cs - aligns the hologram with the real head (patient-to-image registration).
// The user touches each landmark on the patient/phantom with the controller tip and presses the trigger.
// After >= 3 landmarks, a rigid transform (RigidFit.cs: Horn's quaternion method = same result as Kabsch in
// tools/registration.py) moves PatientRoot so the model landmarks coincide with the touched points.
// STATUS: desktop-testable with simulated touches (DesktopViewer.cs); not yet tested on a headset.
using System.Collections.Generic;
using UnityEngine;

namespace SeegPlanner
{
    public class LandmarkRegistration : MonoBehaviour
    {
        public PatientLoader loader;
        public Transform pointerTip;                       // controller tip transform (world space)
        // The touch order comes from headset_manifest.json ("touch_order"), so it always matches the exported landmarks.
        public List<string> Order => loader != null && loader.IsLoaded ? loader.TouchOrder() : new List<string>();

        readonly List<Vector3> modelPts = new();            // landmarks in PatientRoot local space
        readonly List<Vector3> worldPts = new();            // touched positions in world space
        public float LastFreMm { get; private set; }

        public string NextLandmark { get { var o = Order; return modelPts.Count < o.Count ? o[modelPts.Count] : null; } }

        /// Call when the trigger is pressed with the controller tip on the current landmark.
        public void Capture() { if (pointerTip != null) CaptureWorld(pointerTip.position); }

        /// Same as Capture() with an explicit world position (used by the desktop simulation).
        public void CaptureWorld(Vector3 world)
        {
            if (NextLandmark == null) return;
            modelPts.Add(loader.LandmarkLocal(NextLandmark));
            worldPts.Add(world);
            if (modelPts.Count >= 3) Solve();
        }

        public int CapturedCount => modelPts.Count;

        public void ResetCapture() { modelPts.Clear(); worldPts.Clear(); }

        void Solve()
        {
            int n = modelPts.Count;
            var P = new double[n][]; var W = new double[n][];
            for (int i = 0; i < n; i++)
            {
                P[i] = new double[] { modelPts[i].x, modelPts[i].y, modelPts[i].z };
                W[i] = new double[] { worldPts[i].x, worldPts[i].y, worldPts[i].z };
            }
            RigidFit.Solve(P, W, out var q, out var t);              // Horn quaternion, see RigidFit.cs
            // Both point sets are in Unity's frame, so the quaternion applies directly (Unity order: x, y, z, w).
            var rot = new Quaternion((float)q[1], (float)q[2], (float)q[3], (float)q[0]);
            Vector3 cm = Vector3.zero, cw = Vector3.zero;
            for (int i = 0; i < n; i++) { cm += modelPts[i]; cw += worldPts[i]; }
            cm /= n; cw /= n;

            // PatientRoot: world = rot * local + t  ->  t = cw - rot * cm
            var root = loader.PatientRoot;
            root.SetParent(null, true);
            root.rotation = rot;
            root.localScale = Vector3.one;
            root.position = cw - rot * cm;

            double sse = 0;
            for (int i = 0; i < n; i++) sse += (root.TransformPoint(modelPts[i]) - worldPts[i]).sqrMagnitude;
            LastFreMm = (float)(System.Math.Sqrt(sse / n) * 1000.0);
            Debug.Log($"Registration with {n} landmarks: FRE = {LastFreMm:F1} mm");
        }
    }
}
