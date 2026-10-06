// Standalone test of RigidFit.cs (no Unity needed):
//   mcs -out:rigidfit_test.exe unity/Tests/RigidFitTest.cs unity/Assets/SeegPlanner/RigidFit.cs && mono rigidfit_test.exe
using System;
using SeegPlanner;

static class RigidFitTest
{
    static int Main()
    {
        var rng = new Random(1);
        double worstRot = 0, worstT = 0;
        for (int trial = 0; trial < 2000; trial++)
        {
            double[] axis = { rng.NextDouble() - .5, rng.NextDouble() - .5, rng.NextDouble() - .5 };
            double an = Math.Sqrt(axis[0] * axis[0] + axis[1] * axis[1] + axis[2] * axis[2]);
            double ang = rng.NextDouble() * 2 * Math.PI, s = Math.Sin(ang / 2);
            double[] qt = { Math.Cos(ang / 2), s * axis[0] / an, s * axis[1] / an, s * axis[2] / an };
            if (qt[0] < 0) for (int i = 0; i < 4; i++) qt[i] = -qt[i];
            double[] tt = { rng.NextDouble(), rng.NextDouble(), rng.NextDouble() + 0.5 };
            int n = 3 + trial % 3;
            var P = new double[n][]; var W = new double[n][];
            for (int i = 0; i < n; i++)
            {
                P[i] = new[] { (rng.NextDouble() - .5) * 0.18, (rng.NextDouble() - .5) * 0.2, (rng.NextDouble() - .5) * 0.18 };
                var r = RigidFit.Rotate(qt, P[i]);
                W[i] = new[] { r[0] + tt[0], r[1] + tt[1], r[2] + tt[2] };
            }
            RigidFit.Solve(P, W, out var q, out var t);
            double dq = 0, dt = 0;
            for (int i = 0; i < 4; i++) dq = Math.Max(dq, Math.Abs(q[i] - qt[i]));
            for (int i = 0; i < 3; i++) dt = Math.Max(dt, Math.Abs(t[i] - tt[i]));
            worstRot = Math.Max(worstRot, dq); worstT = Math.Max(worstT, dt);
        }
        Console.WriteLine($"2000 random poses, noise-free: max quaternion error {worstRot:E1}, max translation error {worstT * 1000:E1} mm");
        bool ok = worstRot < 1e-6 && worstT < 1e-6;
        Console.WriteLine(ok ? "OK" : "FAIL");
        return ok ? 0 : 1;
    }
}
