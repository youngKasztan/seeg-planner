// LandmarkRegistration.cs - aligns the hologram with the real head (patient-to-image registration).
// The user touches each landmark on the patient/phantom with the controller tip and presses the trigger.
// After >= 3 landmarks, a rigid transform (Horn's quaternion method = same result as Kabsch in
// tools/registration.py) moves PatientRoot so the model landmarks coincide with the touched points.
// STATUS: not yet compiled in a Unity project.
using System.Collections.Generic;
using UnityEngine;

namespace SeegPlanner
{
    public class LandmarkRegistration : MonoBehaviour
    {
        public PatientLoader loader;
        public Transform pointerTip;                       // controller tip transform (world space)
        public string[] landmarkOrder = { "nose_tip", "nasion", "left_preauricular", "right_preauricular", "vertex" };

        readonly List<Vector3> modelPts = new();            // landmarks in PatientRoot local space
        readonly List<Vector3> worldPts = new();            // touched positions in world space
        public float LastFreMm { get; private set; }

        public string NextLandmark => modelPts.Count < landmarkOrder.Length ? landmarkOrder[modelPts.Count] : null;

        /// Call when the trigger is pressed with the controller tip on the current landmark.
        public void Capture()
        {
            if (NextLandmark == null) return;
            modelPts.Add(loader.LandmarkLocal(NextLandmark));
            worldPts.Add(pointerTip.position);
            if (modelPts.Count >= 3) Solve();
        }

        public void ResetCapture() { modelPts.Clear(); worldPts.Clear(); }

        void Solve()
        {
            int n = modelPts.Count;
            Vector3 cm = Vector3.zero, cw = Vector3.zero;
            for (int i = 0; i < n; i++) { cm += modelPts[i]; cw += worldPts[i]; }
            cm /= n; cw /= n;

            // cross-covariance S = sum (m - cm)(w - cw)^T
            float sxx = 0, sxy = 0, sxz = 0, syx = 0, syy = 0, syz = 0, szx = 0, szy = 0, szz = 0;
            for (int i = 0; i < n; i++)
            {
                Vector3 a = modelPts[i] - cm, b = worldPts[i] - cw;
                sxx += a.x * b.x; sxy += a.x * b.y; sxz += a.x * b.z;
                syx += a.y * b.x; syy += a.y * b.y; syz += a.y * b.z;
                szx += a.z * b.x; szy += a.z * b.y; szz += a.z * b.z;
            }
            // Horn's symmetric 4x4 matrix; its top eigenvector is the optimal rotation quaternion (w, x, y, z)
            double[,] N = {
                { sxx + syy + szz, syz - szy,        szx - sxz,        sxy - syx },
                { syz - szy,       sxx - syy - szz,  sxy + syx,        szx + sxz },
                { szx - sxz,       sxy + syx,       -sxx + syy - szz,  syz + szy },
                { sxy - syx,       szx + sxz,        syz + szy,       -sxx - syy + szz } };
            double shift = 0; for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) shift += System.Math.Abs(N[i, j]);
            for (int i = 0; i < 4; i++) N[i, i] += shift;                // make positive definite for power iteration
            double[] q = { 1, 0, 0, 0 };
            for (int it = 0; it < 200; it++)
            {
                double[] r = new double[4];
                for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) r[i] += N[i, j] * q[j];
                double norm = System.Math.Sqrt(r[0] * r[0] + r[1] * r[1] + r[2] * r[2] + r[3] * r[3]);
                for (int i = 0; i < 4; i++) q[i] = r[i] / norm;
            }
            // Unity's left-handed frame mirrors handedness of both point sets equally, so the rotation is valid.
            var rot = new Quaternion((float)q[1], (float)q[2], (float)q[3], (float)q[0]);

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
