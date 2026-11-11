// AprilTagCameraSource.cs - finds AprilTags (family tagStandard41h12) in the Quest 3 passthrough camera image and
// reports their world poses to HeadMarkerTracker as "TAG-<id>".
//
// Pipeline (one image at a time, up to maxRateHz):
//   ARCameraManager.TryAcquireLatestCpuImage (Unity OpenXR: Meta, left RGB camera, YUV -> we use the Y plane)
//   -> background thread: AprilTag detector (package jp.keijiro.apriltag, native) + pose estimation with the real
//      camera intrinsics (tag pose in the OpenCV camera frame: x right, y down, z forward)
//   -> main thread: camera pose in the world = head pose AT CAPTURE TIME * camera-in-head (Camera2 LENS_POSE_*,
//      converted exactly like Meta's PassthroughCameraUtils) -> tag pose in the world -> HeadMarkerTracker.Report.
//
// Project settings (Unity OpenXR: Meta 2.6):
//   Project Settings > XR Plug-in Management > OpenXR (Android) > Meta Quest feature group >
//   gear of "Meta Quest: Camera (Passthrough)" > enable "Camera Image Support". This adds the camera permissions
//   (horizonos.permission.HEADSET_CAMERA, ...) to the Android manifest. The permission is requested here at start;
//   after "Allow" the camera subsystem is restarted automatically.
//
// Tag size = edge of the INNER square of a tagStandard41h12 tag (5 of its 9 cells), nominal size from the printed
// sheet (tools/make_apriltag_markers.py) times HeadMarkerTracker.printScale.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
using ATI = AprilTag.Interop;

namespace SeegPlanner
{
    public class AprilTagCameraSource : MonoBehaviour
    {
        public HeadMarkerTracker tracker;
        [Tooltip("Nominal inner-square size (mm) of tags 0-2 on the printed sheet (headband set)")]
        public float headbandTagMm = 40f;
        [Tooltip("Nominal inner-square size (mm) of the large tag (id 3) on the printed sheet")]
        public float largeTagMm = 55f;
        public int largeTagId = 3;
        [Tooltip("Max. number of camera images analysed per second")]
        public float maxRateHz = 15f;
        [Tooltip("AprilTag quad decimation (2 = faster, 1 = finds smaller / farther tags)")]
        public float decimation = 2f;
        [Tooltip("Detections with a lower decision margin are ignored (bad / blurred tags)")]
        public float minDecisionMargin = 25f;
        [Tooltip("Used when the image timestamp cannot be matched to the head pose clock (seconds)")]
        public float fallbackLatency = 0.05f;
        [Tooltip("Draw a green frame on every detected tag (should sit exactly on the inner white square)")]
        public bool showOverlay = true;

        const string CameraPermission = "horizonos.permission.HEADSET_CAMERA";

        ARCameraManager cameraManager;
        Transform head;
        bool restartCamera, permissionAsked;
        string state = "starting";
        float startTime;

        // camera intrinsics (pixels, for the image as delivered) and the camera pose in the head frame
        Pose lensInHead = Pose.identity; bool lensKnown; string lensInfo = "";
        float fallbackFx, fallbackFy, fallbackCx, fallbackCy; int fallbackW, fallbackH;   // Camera2, full sensor

        // detector (used by one background task at a time)
        ATI.Detector detector; ATI.Family family; ATI.ImageU8 image;
        byte[] gray; int imgW, imgH;
        Task<List<Detection>> job;
        Capture jobCapture;
        double lastImageTimestamp = -1;
        float lastStart;

        // statistics for the status line
        int framesDone; float statT0; float rateHz; float lastLatencyMs; string clockUsed = "";
        int tagsLast;

        struct Detection { public int id; public Vector3 pos; public Quaternion rot; public float size; public float margin; }
        struct Capture { public Vector3 headPos; public Quaternion headRot; public double fx, fy, cx, cy; }

        // head pose history, to look up the head pose at the moment the camera image was taken
        struct HeadSample { public double t; public Vector3 p; public Quaternion r; }
        readonly HeadSample[] history = new HeadSample[128];
        int historyCount, historyNext;

        readonly Dictionary<int, Transform> overlays = new();

        // ---------------------------------------------------------------- start / permission

        void Start()
        {
            startTime = Time.time;
            cameraManager = FindAnyObjectByType<ARCameraManager>();
            head = Camera.main != null ? Camera.main.transform : null;
            if (cameraManager == null) { state = "no ARCameraManager in the scene"; return; }
            ReadCamera2Metadata();
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(CameraPermission))
            {
                permissionAsked = true;
                var cb = new UnityEngine.Android.PermissionCallbacks();
                cb.PermissionGranted += _ => restartCamera = true;      // camera subsystem checks it only on start
                cb.PermissionDenied += _ => state = "camera permission DENIED";
                UnityEngine.Android.Permission.RequestUserPermission(CameraPermission, cb);
            }
#endif
        }

        void OnDestroy()
        {
            if (job != null) { try { job.Wait(1000); } catch { } }
            detector?.Dispose(); family?.Dispose(); image?.Dispose();
        }

        bool HasPermission()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            return UnityEngine.Android.Permission.HasUserAuthorizedPermission(CameraPermission);
#else
            return true;
#endif
        }

        // ---------------------------------------------------------------- per frame

        void LateUpdate()
        {
            if (head == null && Camera.main != null) head = Camera.main.transform;
            if (head != null) RecordHead(Time.realtimeSinceStartupAsDouble, head.position, head.rotation);
            if (cameraManager == null) { Publish(); return; }

            if (restartCamera)                                      // permission just granted: restart the subsystem
            {
                restartCamera = false;
                cameraManager.enabled = false;
                cameraManager.enabled = true;
                state = "camera permission granted, starting camera";
            }

            if (job != null && job.IsCompleted) FinishJob();
            if (job == null && Time.time - lastStart >= 1f / Mathf.Max(1f, maxRateHz)) TryStartJob();
            Publish();
        }

        void TryStartJob()
        {
            if (!HasPermission()) { state = permissionAsked ? "waiting for camera permission" : "no camera permission"; return; }
            if (!cameraManager.TryAcquireLatestCpuImage(out XRCpuImage cpu))
            {
                if (Time.time - startTime > 8f)
                    state = "no camera image - enable 'Camera Image Support' (Meta Quest: Camera (Passthrough))";
                return;
            }
            using (cpu)
            {
                if (cpu.timestamp == lastImageTimestamp) return;   // same image as last time
                lastImageTimestamp = cpu.timestamp;
                if (!CopyLuma(cpu)) return;

                // intrinsics for this image size
                if (!GetIntrinsics(cpu.width, cpu.height, out var fx, out var fy, out var cx, out var cy))
                { state = "no camera intrinsics"; return; }

                // head pose when the image was taken
                double age = ImageAge(cpu.timestamp);
                lastLatencyMs = (float)(age * 1000.0);
                HeadAt(Time.realtimeSinceStartupAsDouble - age, out var hp, out var hr);

                EnsureDetector(cpu.width, cpu.height);
                jobCapture = new Capture { headPos = hp, headRot = hr, fx = fx, fy = fy, cx = cx, cy = cy };
                var cap = jobCapture;
                float printScale = tracker != null ? tracker.printScale : 1f;
                float sizeSmall = headbandTagMm * 0.001f * printScale, sizeLarge = largeTagMm * 0.001f * printScale;
                int large = largeTagId; float minMargin = minDecisionMargin;
                lastStart = Time.time;
                state = "running";
                job = Task.Run(() => Detect(cap, sizeSmall, sizeLarge, large, minMargin));
            }
        }

        bool CopyLuma(XRCpuImage cpu)
        {
            if (cpu.planeCount < 1) { state = "camera image has no planes"; return false; }
            var plane = cpu.GetPlane(0);                            // Y plane of YUV_420_888 / the only plane of R8
            int w = cpu.width, h = cpu.height;
            if (plane.pixelStride != 1) { state = $"unexpected pixel stride {plane.pixelStride}"; return false; }
            if (gray == null || gray.Length != w * h) gray = new byte[w * h];
            var src = plane.data;
            if ((long)plane.rowStride * (h - 1) + w > src.Length) { state = "camera image smaller than expected"; return false; }
            for (int y = 0; y < h; y++)
                Unity.Collections.NativeArray<byte>.Copy(src, y * plane.rowStride, gray, y * w, w);
            return true;
        }

        void EnsureDetector(int w, int h)
        {
            if (detector != null && imgW == w && imgH == h) { detector.QuadDecimate = decimation; return; }
            detector?.Dispose(); family?.Dispose(); image?.Dispose();
            detector = ATI.Detector.Create();
            family = ATI.Family.CreateTagStandard41h12();
            detector.ThreadCount = Mathf.Clamp(SystemInfo.processorCount - 1, 1, 4);
            detector.QuadDecimate = decimation;
            detector.AddFamily(family);
            image = ATI.ImageU8.Create(w, h);
            imgW = w; imgH = h;
        }

        // ---------------------------------------------------------------- background thread

        List<Detection> Detect(Capture cap, float sizeSmall, float sizeLarge, int largeId, float minMargin)
        {
            var result = new List<Detection>();
            var buf = image.Buffer; int stride = image.Stride;
            for (int y = 0; y < imgH; y++)
                new ReadOnlySpan<byte>(gray, y * imgW, imgW).CopyTo(buf.Slice(y * stride, imgW));

            using var dets = detector.Detect(image);
            for (int i = 0; i < dets.Length; i++)
            {
                ref var d = ref dets[i];
                if (d.Hamming > 1 || d.DecisionMargin < minMargin) continue;
                float size = d.ID == largeId ? sizeLarge : sizeSmall;
                var info = new ATI.DetectionInfo(ref d, size, cap.fx, cap.fy, cap.cx, cap.cy);
                using var pose = new ATI.Pose(ref info);
                // OpenCV camera frame (x right, y down, z forward) -> Unity camera frame (x right, y up, z forward):
                // p' = S p, R' = S R S with S = diag(1, -1, 1)
                var t = pose.t; var R = pose.R;
                var pos = new Vector3((float)t.e0, -(float)t.e1, (float)t.e2);
                var rot = FromMatrix(R.e00, -R.e01, R.e02,
                                     -R.e10, R.e11, -R.e12,
                                     R.e20, -R.e21, R.e22);
                result.Add(new Detection { id = d.ID, pos = pos, rot = rot, size = size, margin = d.DecisionMargin });
            }
            return result;
        }

        /// Rotation matrix (row-major m[row,col]) -> quaternion, without Unity API calls (runs off the main thread).
        static Quaternion FromMatrix(double m00, double m01, double m02, double m10, double m11, double m12,
                                     double m20, double m21, double m22)
        {
            double tr = m00 + m11 + m22, x, y, z, w;
            if (tr > 0) { double s = Math.Sqrt(tr + 1.0) * 2; w = 0.25 * s; x = (m21 - m12) / s; y = (m02 - m20) / s; z = (m10 - m01) / s; }
            else if (m00 > m11 && m00 > m22) { double s = Math.Sqrt(1.0 + m00 - m11 - m22) * 2; w = (m21 - m12) / s; x = 0.25 * s; y = (m01 + m10) / s; z = (m02 + m20) / s; }
            else if (m11 > m22) { double s = Math.Sqrt(1.0 + m11 - m00 - m22) * 2; w = (m02 - m20) / s; x = (m01 + m10) / s; y = 0.25 * s; z = (m12 + m21) / s; }
            else { double s = Math.Sqrt(1.0 + m22 - m00 - m11) * 2; w = (m10 - m01) / s; x = (m02 + m20) / s; y = (m12 + m21) / s; z = 0.25 * s; }
            return new Quaternion((float)x, (float)y, (float)z, (float)w);
        }

        // ---------------------------------------------------------------- results (main thread)

        void FinishJob()
        {
            List<Detection> dets = null;
            try { dets = job.Result; }
            catch (Exception e) { state = "detector error: " + e.GetBaseException().Message; Debug.LogException(e); }
            job = null;
            framesDone++;
            if (Time.time - statT0 > 2f) { rateHz = framesDone / (Time.time - statT0); framesDone = 0; statT0 = Time.time; }
            if (dets == null) return;
            tagsLast = dets.Count;

            // camera pose in the world at capture time
            Vector3 camPos = jobCapture.headPos + jobCapture.headRot * lensInHead.position;
            Quaternion camRot = jobCapture.headRot * lensInHead.rotation;
            var seen = new HashSet<int>();
            foreach (var d in dets)
            {
                Vector3 wp = camPos + camRot * d.pos;
                Quaternion wr = camRot * d.rot;
                tracker?.Report("TAG-" + d.id, wp, wr);
                if (showOverlay) ShowOverlay(d.id, wp, wr, d.size);
                seen.Add(d.id);
            }
            foreach (var kv in overlays)
                if (!seen.Contains(kv.Key) && kv.Value.gameObject.activeSelf) kv.Value.gameObject.SetActive(false);
        }

        void Publish()
        {
            if (tracker == null) return;
            string lens = lensKnown ? "" : " | camera pose: DEFAULT (" + lensInfo + ")";
            tracker.SourceStatus = state == "running"
                ? $"AprilTag camera {rateHz:F0} Hz, {tagsLast} tag(s), latency {lastLatencyMs:F0} ms{clockUsed}{lens}"
                : "AprilTag camera: " + state + lens;
        }

        // ---------------------------------------------------------------- intrinsics, lens pose, timing

        bool GetIntrinsics(int w, int h, out double fx, out double fy, out double cx, out double cy)
        {
            fx = fy = cx = cy = 0;
            if (cameraManager.TryGetIntrinsics(out XRCameraIntrinsics k) && k.resolution.x > 0)
            {
                double sx = (double)w / k.resolution.x, sy = (double)h / k.resolution.y;
                fx = k.focalLength.x * sx; fy = k.focalLength.y * sy; cx = k.principalPoint.x * sx; cy = k.principalPoint.y * sy;
                return true;
            }
            if (fallbackW > 0)                                       // Camera2 values for the full sensor
            {
                double sx = (double)w / fallbackW, sy = (double)h / fallbackH;
                fx = fallbackFx * sx; fy = fallbackFy * sy; cx = fallbackCx * sx; cy = fallbackCy * sy;
                return true;
            }
            return false;
        }

        /// Reads the left passthrough camera's pose in the head frame (and intrinsics as a fallback) from Android
        /// Camera2, with Meta's metadata keys - same conversion as Meta's PassthroughCameraUtils.
        void ReadCamera2Metadata()
        {
            lensInfo = "not read";
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using var activity = new AndroidJavaClass("com.unity3d.player.UnityPlayer").GetStatic<AndroidJavaObject>("currentActivity");
                using var manager = activity.Call<AndroidJavaObject>("getSystemService", "camera");
                using var keys = new AndroidJavaClass("android.hardware.camera2.CameraCharacteristics");
                string[] ids = manager.Call<string[]>("getCameraIdList");
                foreach (var id in ids)
                {
                    using var ch = manager.Call<AndroidJavaObject>("getCameraCharacteristics", id);
                    int source = -1, position = -1;
                    using (var list = ch.Call<AndroidJavaObject>("getKeys"))
                    {
                        int n = list.Call<int>("size");
                        for (int i = 0; i < n; i++)
                        {
                            using var key = list.Call<AndroidJavaObject>("get", i);
                            string name = key.Call<string>("getName");
                            if (name == "com.meta.extra_metadata.camera_source") source = FirstByte(ch.Call<sbyte[]>("get", key));
                            else if (name == "com.meta.extra_metadata.position") position = FirstByte(ch.Call<sbyte[]>("get", key));
                        }
                    }
                    if (source != 0 || position != 0) continue;         // want: passthrough camera (0), left (0)

                    using var kT = keys.GetStatic<AndroidJavaObject>("LENS_POSE_TRANSLATION");
                    using var kR = keys.GetStatic<AndroidJavaObject>("LENS_POSE_ROTATION");
                    float[] t = ch.Call<float[]>("get", kT), r = ch.Call<float[]>("get", kR);
                    if (t != null && t.Length >= 3 && r != null && r.Length >= 4)
                    {
                        var pHeadFromCam = new Vector3(t[0], t[1], -t[2]);
                        var qCamFromHead = new Quaternion(-r[0], -r[1], r[2], r[3]);
                        // Meta: worldFromCamera = worldFromHead * headFromCamera, then orientation *= Euler(180, 0, 0)
                        lensInHead = new Pose(pHeadFromCam, Quaternion.Inverse(qCamFromHead) * Quaternion.Euler(180f, 0f, 0f));
                        lensKnown = true;
                        lensInfo = $"camera {id}: t=({t[0]:F3},{t[1]:F3},{t[2]:F3}) q=({r[0]:F3},{r[1]:F3},{r[2]:F3},{r[3]:F3})";
                    }
                    using var kK = keys.GetStatic<AndroidJavaObject>("LENS_INTRINSIC_CALIBRATION");
                    using var kA = keys.GetStatic<AndroidJavaObject>("SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE");
                    float[] k = ch.Call<float[]>("get", kK);
                    using var arr = ch.Call<AndroidJavaObject>("get", kA);
                    if (k != null && k.Length >= 4 && arr != null)
                    {
                        fallbackFx = k[0]; fallbackFy = k[1]; fallbackCx = k[2]; fallbackCy = k[3];
                        fallbackW = arr.Get<int>("right"); fallbackH = arr.Get<int>("bottom");
                    }
                    break;
                }
                if (!lensKnown) lensInfo = "left passthrough camera not found in Camera2 (" + ids.Length + " cameras)";
            }
            catch (Exception e) { lensInfo = "Camera2 error: " + e.Message; }
            Debug.Log("[AprilTagCameraSource] " + lensInfo + $", fallback intrinsics f=({fallbackFx},{fallbackFy}) c=({fallbackCx},{fallbackCy}) {fallbackW}x{fallbackH}");
#endif
        }

        static int FirstByte(sbyte[] a) => a != null && a.Length > 0 ? a[0] : -1;

        /// How old the camera image is (seconds). The image timestamp comes from the camera clock; we compare it with
        /// Android's two candidate clocks and take the one that gives a plausible age (0-300 ms).
#if UNITY_ANDROID && !UNITY_EDITOR
        AndroidJavaClass sysClock, javaSystem;
#endif
        double ImageAge(double imageTimestamp)
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                sysClock ??= new AndroidJavaClass("android.os.SystemClock");
                javaSystem ??= new AndroidJavaClass("java.lang.System");
                double boot = sysClock.CallStatic<long>("elapsedRealtimeNanos") * 1e-9;
                double mono = javaSystem.CallStatic<long>("nanoTime") * 1e-9;
                foreach (var scale in new[] { 1.0, 1e-9, 1e-6 })   // timestamp may be in s, ns or us
                {
                    double ts = imageTimestamp * scale;
                    double a = boot - ts; if (a >= 0 && a < 0.3) { clockUsed = ""; return a; }
                    a = mono - ts; if (a >= 0 && a < 0.3) { clockUsed = ""; return a; }
                }
            }
            catch { }
#endif
            clockUsed = " (assumed)";
            return fallbackLatency;
        }

        void RecordHead(double t, Vector3 p, Quaternion r)
        {
            history[historyNext] = new HeadSample { t = t, p = p, r = r };
            historyNext = (historyNext + 1) % history.Length;
            if (historyCount < history.Length) historyCount++;
        }

        void HeadAt(double t, out Vector3 p, out Quaternion r)
        {
            p = head != null ? head.position : Vector3.zero; r = head != null ? head.rotation : Quaternion.identity;
            HeadSample newer = default; bool haveNewer = false;
            for (int i = 1; i <= historyCount; i++)
            {
                var s = history[(historyNext - i + history.Length) % history.Length];
                if (s.t <= t)
                {
                    if (!haveNewer) { p = s.p; r = s.r; return; }
                    float k = (float)((t - s.t) / Math.Max(1e-6, newer.t - s.t));
                    p = Vector3.Lerp(s.p, newer.p, k); r = Quaternion.Slerp(s.r, newer.r, k);
                    return;
                }
                newer = s; haveNewer = true;
            }
            if (haveNewer) { p = newer.p; r = newer.r; }
        }

        // ---------------------------------------------------------------- overlay

        void ShowOverlay(int id, Vector3 pos, Quaternion rot, float size)
        {
            if (!overlays.TryGetValue(id, out var t))
            {
                var go = new GameObject("AprilTagOverlay_" + id);
                go.AddComponent<MeshFilter>().sharedMesh = FrameMesh(0.08f);
                var mat = PatientLoader.SolidMaterial(new Color(0.1f, 1f, 0.2f));
                var mr = go.AddComponent<MeshRenderer>();
                if (mat != null) mr.sharedMaterial = mat;
                t = go.transform;
                overlays[id] = t;
            }
            t.gameObject.SetActive(true);
            t.SetPositionAndRotation(pos, rot);
            t.localScale = Vector3.one * size;
        }

        /// Unit square frame in the XY plane (tag plane), border width `w` (fraction of the edge), both sides visible.
        static Mesh FrameMesh(float w)
        {
            float a = 0.5f, b = 0.5f - w;
            var v = new[] {
                new Vector3(-a,-a,0), new Vector3(a,-a,0), new Vector3(a,a,0), new Vector3(-a,a,0),
                new Vector3(-b,-b,0), new Vector3(b,-b,0), new Vector3(b,b,0), new Vector3(-b,b,0) };
            var tris = new List<int>();
            for (int i = 0; i < 4; i++)
            {
                int o0 = i, o1 = (i + 1) % 4, i0 = 4 + i, i1 = 4 + (i + 1) % 4;
                tris.AddRange(new[] { o0, o1, i1, o0, i1, i0, o0, i1, o1, o0, i0, i1 });   // both windings
            }
            var m = new Mesh { vertices = v, triangles = tris.ToArray() };
            m.RecalculateNormals(); m.RecalculateBounds();
            return m;
        }
    }
}
