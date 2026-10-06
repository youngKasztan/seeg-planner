// RigidFit.cs - least-squares rigid transform between two point sets (Horn 1987, closed-form quaternion).
// Pure C# (no Unity types) so it can be unit-tested outside Unity: see unity/Tests/RigidFitTest.cs.
// Same result as kabsch() in tools/registration.py.
namespace SeegPlanner
{
    public static class RigidFit
    {
        /// Finds rotation q = (w, x, y, z) and translation t minimising sum |R(q) p_i + t - w_i|^2.
        public static void Solve(double[][] P, double[][] W, out double[] q, out double[] t)
        {
            int n = P.Length;
            double[] cp = new double[3], cw = new double[3];
            for (int i = 0; i < n; i++) for (int k = 0; k < 3; k++) { cp[k] += P[i][k] / n; cw[k] += W[i][k] / n; }
            double[,] S = new double[3, 3];                     // cross-covariance sum (p - cp)(w - cw)^T
            for (int i = 0; i < n; i++)
                for (int a = 0; a < 3; a++) for (int b = 0; b < 3; b++) S[a, b] += (P[i][a] - cp[a]) * (W[i][b] - cw[b]);
            double sxx = S[0, 0], sxy = S[0, 1], sxz = S[0, 2], syx = S[1, 0], syy = S[1, 1], syz = S[1, 2],
                   szx = S[2, 0], szy = S[2, 1], szz = S[2, 2];
            double[,] N = {
                { sxx + syy + szz, syz - szy,        szx - sxz,        sxy - syx },
                { syz - szy,       sxx - syy - szz,  sxy + syx,        szx + sxz },
                { szx - sxz,       sxy + syx,       -sxx + syy - szz,  syz + szy },
                { sxy - syx,       szx + sxz,        syz + szy,       -sxx - syy + szz } };
            q = LargestEigenvector(N);
            t = new double[3];
            double[] rc = Rotate(q, cp);
            for (int k = 0; k < 3; k++) t[k] = cw[k] - rc[k];
        }

        public static double[] Rotate(double[] q, double[] v)
        {
            double w = q[0], x = q[1], y = q[2], z = q[3];
            return new[] {
                (1 - 2 * (y * y + z * z)) * v[0] + 2 * (x * y - w * z) * v[1] + 2 * (x * z + w * y) * v[2],
                2 * (x * y + w * z) * v[0] + (1 - 2 * (x * x + z * z)) * v[1] + 2 * (y * z - w * x) * v[2],
                2 * (x * z - w * y) * v[0] + 2 * (y * z + w * x) * v[1] + (1 - 2 * (x * x + y * y)) * v[2] };
        }

        /// Cyclic Jacobi eigen-decomposition of a symmetric 4x4 matrix; returns the unit eigenvector
        /// of the largest eigenvalue (robust, unlike power iteration when eigenvalues are close).
        static double[] LargestEigenvector(double[,] A0)
        {
            const int n = 4;
            double[,] A = (double[,])A0.Clone(), V = new double[n, n];
            for (int i = 0; i < n; i++) V[i, i] = 1;
            for (int sweep = 0; sweep < 50; sweep++)
            {
                double off = 0;
                for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++) off += A[i, j] * A[i, j];
                if (off < 1e-30) break;
                for (int p = 0; p < n; p++)
                    for (int r = p + 1; r < n; r++)
                    {
                        if (System.Math.Abs(A[p, r]) < 1e-300) continue;
                        double theta = (A[r, r] - A[p, p]) / (2 * A[p, r]);
                        double tt = System.Math.Sign(theta) / (System.Math.Abs(theta) + System.Math.Sqrt(theta * theta + 1));
                        if (theta == 0) tt = 1;
                        double c = 1 / System.Math.Sqrt(tt * tt + 1), s = tt * c;
                        for (int k = 0; k < n; k++)
                        {
                            double akp = A[k, p], akr = A[k, r];
                            A[k, p] = c * akp - s * akr; A[k, r] = s * akp + c * akr;
                        }
                        for (int k = 0; k < n; k++)
                        {
                            double apk = A[p, k], ark = A[r, k];
                            A[p, k] = c * apk - s * ark; A[r, k] = s * apk + c * ark;
                        }
                        for (int k = 0; k < n; k++)
                        {
                            double vkp = V[k, p], vkr = V[k, r];
                            V[k, p] = c * vkp - s * vkr; V[k, r] = s * vkp + c * vkr;
                        }
                    }
            }
            int best = 0;
            for (int i = 1; i < n; i++) if (A[i, i] > A[best, best]) best = i;
            double[] q = { V[0, best], V[1, best], V[2, best], V[3, best] };
            double norm = System.Math.Sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
            for (int i = 0; i < 4; i++) q[i] /= norm;
            if (q[0] < 0) for (int i = 0; i < 4; i++) q[i] = -q[i];
            return q;
        }
    }
}
