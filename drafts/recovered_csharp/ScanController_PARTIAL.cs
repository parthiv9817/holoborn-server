// SOURCE: Recovered ~60% from web chat 2026-05-05 (originally April 28 doc, pre-burst era)
// STATUS: PARTIAL — TREAT AS ARCHITECTURAL REFERENCE, NOT VERBATIM PORT
//
// CRITICAL DIVERGENCES FROM SHIPPED APK (verified by user 2026-05-05):
// 1. INPUT MAPPING — keep recovered A-button (revolve), add new X-button (burst).
//    Shipped: A (right primaryButton) = 30-frame revolve scan ✅ matches recovered
//             X (left  primaryButton) = burst 5-frame same-position capture ⚠️ NEW, not in recovered
//    CLAUDE.md was wrong about input mapping — disregard.
// 2. NO BURST CAPTURE PATH in recovered code. Must be added on X button.
//    Shipped flow: 5 frames captured ~40ms apart, all angles=0.0, POST /generate-multiview
//    No /validate-frame call before burst (per user's memory of shipped behavior).
//
// MISSING METHOD BODIES (write fresh from spec — see project_phoenix_war_plan.md):
//   - Update() — state dispatcher
//   - UpdateIdle() — checks button presses, runs validation
//   - UpdateScanning() invoker (body present below)
//   - ValidateAndStartScan() — coroutine: capture → POST /validate-frame → if good, StartScanAt
//   - StartScanAt(Vector3 pos, byte[] initialFrame) — sets subjectWorldPos, transitions state
//   - CaptureFrame() — Graphics.Blit + ReadPixels + EncodeToJPG (pattern documented in prose)
//   - MarkNearestDot()
//   - DestroyScanGuides()
//   - PollAndDownloadGLB(string taskId) — poll /generate/{id}/status every 3s
//   - SpawnPlaceholder() — spawn mascot at 1.5m forward
//   - LoadAndInstantiateGLB(byte[] glbData) — glTFast load + spawn
//   - TestLoadGLB() — B-button test loader
//   - SpawnGLBFromBytes(byte[], string) — shared helper (auto-scale to 1.7m, floor align,
//                                          shader fallback for stripped URP materials)

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Networking;

public class ScanController : MonoBehaviour
{
    // === Configuration ===
    [Header("Server")]
    public string serverUrl = "https://YOUR-NGROK-URL.ngrok-free.app";

    [Header("References")]
    public Transform headTransform;        // CenterEyeAnchor
    public GameObject placeholderAvatarPrefab;

    [Header("Debug")]
    public bool debugMode = false;

    // === Constants ===
    private const int MaxFrames = 30;
    private const float DegreesPerCapture = 12f;  // 360 / 30

    // === State ===
    private enum ScanState { IDLE, SCANNING, COMPLETE }
    private ScanState state = ScanState.IDLE;

    // === Input ===
    // ✅ REBUILD MAPPING per shipped APK (user-verified 2026-05-05):
    //    A button (right primaryButton) = 30-frame REVOLVE scan ← keep recovered logic
    //    X button (left  primaryButton) = BURST capture 5 frames @ 0° angles ← NEW logic
    private InputAction revolveAction;       // A (right primaryButton) — 30-frame revolve scan
    private InputAction burstAction;         // X (left  primaryButton) — burst 5-frame same-position

    private bool buttonTriggered = false;
    private bool singleFrameTriggered = false;
    private bool singleFrameRunning = false;
    private bool isValidating = false;

    // === Camera ===
    private PassthroughCameraAccess cameraAccess;

    // === Scan tracking ===
    private Vector3 subjectWorldPos;
    private float previousAngle;
    private float cumulativeAngle;
    private float lastCaptureAngle;
    private float scanRadius;
    private float scanStartAngle;

    // === Captured data ===
    private List<CapturedFrame> capturedFrames = new List<CapturedFrame>();

    [Serializable]
    private class CapturedFrame
    {
        public byte[] jpeg;
        public float angleDegrees;
    }

    // === AR guides ===
    private GameObject floorMarker;
    private GameObject ringObj;
    private GameObject directionArrow;
    private List<GameObject> captureDots = new List<GameObject>();
    private bool[] dotCaptured;

    // === Response classes ===
    [Serializable] private class FramingResponse { public string framing; public string message; }
    [Serializable] private class MultiviewResponse { public string status; public string task_id; public int frames_received; }
    [Serializable] private class StatusResponse { public string status; public int progress; public string glb_url; }

    // =========================================================
    // LIFECYCLE — only Start partial recovered
    // =========================================================

    /* RECOVERED PARTIAL — DO NOT carry the input bindings as-is, REBUILD per shipped mapping
    void Start()
    {
        cameraAccess = FindFirstObjectByType<PassthroughCameraAccess>();

        // RECOVERED: A button = revolve, X button = single  ❌ INVERTED FROM SHIPPED
        // REBUILD:   A button = BURST,   X button = validate

        var avatarSpawner = FindFirstObjectByType<AvatarSpawner>();
        if (avatarSpawner != null)
            avatarSpawner.enabled = false;
    }
    */

    // =========================================================
    // SCANNING STATE — AUTO-CAPTURE EVERY 12 DEGREES (RECOVERED VERBATIM)
    // This logic is correct for X-button revolve mode. Reuse as-is.
    // =========================================================

    void UpdateScanning()
    {
        if (capturedFrames.Count >= MaxFrames)
        {
            TransitionToComplete();
            return;
        }

        UpdateArrowPosition();

        Vector3 headFlat = new Vector3(headTransform.position.x, 0, headTransform.position.z);
        Vector3 subjectFlat = new Vector3(subjectWorldPos.x, 0, subjectWorldPos.z);
        Vector3 toSubject = subjectFlat - headFlat;
        float currentAngle = Mathf.Atan2(toSubject.z, toSubject.x) * Mathf.Rad2Deg;

        float frameDelta = Mathf.DeltaAngle(previousAngle, currentAngle);
        cumulativeAngle += frameDelta;
        previousAngle = currentAngle;

        float absCumulative = Mathf.Abs(cumulativeAngle);

        if (absCumulative - lastCaptureAngle >= DegreesPerCapture)
        {
            byte[] jpegBytes = CaptureFrame();
            if (jpegBytes != null)
            {
                capturedFrames.Add(new CapturedFrame
                {
                    jpeg = jpegBytes,
                    angleDegrees = cumulativeAngle
                });
                lastCaptureAngle = absCumulative;
                MarkNearestDot();
                SetStatus($"{capturedFrames.Count}/{MaxFrames} frames captured", Color.yellow);
            }
        }
    }

    void TransitionToComplete()
    {
        state = ScanState.COMPLETE;
        DestroyScanGuides();
        StartCoroutine(UploadAndSpawn());
    }

    // =========================================================
    // ★★★ HTTP CONTRACT — LOCKED BETWEEN QUEST + MAC BACKEND ★★★
    // This must match holoborn-server/app/routes/generation.py /generate-multiview
    // RECOVERED VERBATIM. Use as-is. Frame field names MUST be `frame_0..frame_N`,
    // metadata MUST be `metadata` form field with JSON of [{index, angle}, ...]
    // =========================================================

    IEnumerator UploadAndSpawn()
    {
        SetStatus($"Uploading {capturedFrames.Count} frames...", Color.yellow);

        var form = new List<IMultipartFormSection>();

        for (int i = 0; i < capturedFrames.Count; i++)
        {
            form.Add(new MultipartFormFileSection(
                $"frame_{i}",
                capturedFrames[i].jpeg,
                $"frame_{i}.jpg",
                "image/jpeg"
            ));
        }

        string metaJson = "[";
        for (int i = 0; i < capturedFrames.Count; i++)
        {
            if (i > 0) metaJson += ",";
            metaJson += "{\"index\":" + i + ",\"angle\":"
                     + capturedFrames[i].angleDegrees.ToString("F1") + "}";
        }
        metaJson += "]";
        form.Add(new MultipartFormDataSection("metadata", metaJson));

        using (UnityWebRequest req = UnityWebRequest.Post(
            serverUrl + "/generate-multiview", form))
        {
            req.timeout = 120;
            req.certificateHandler = new BypassCertificate();

            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                SetStatus($"Upload failed: {req.error}", Color.red);
                yield break;
            }

            var response = JsonUtility.FromJson<MultiviewResponse>(req.downloadHandler.text);
            SpawnPlaceholder();
            yield return StartCoroutine(PollAndDownloadGLB(response.task_id));
        }
    }

    // =========================================================
    // AR SCAN GUIDES (RECOVERED VERBATIM — reuse for X-button revolve mode)
    // =========================================================

    void SpawnScanGuides()
    {
        Vector3 headFlat = new Vector3(headTransform.position.x, 0, headTransform.position.z);
        Vector3 subjectFlat = new Vector3(subjectWorldPos.x, 0, subjectWorldPos.z);
        Vector3 toSubject = subjectFlat - headFlat;

        scanRadius = Vector3.Distance(headFlat, subjectFlat);
        if (scanRadius < 0.5f) scanRadius = 2f;

        scanStartAngle = Mathf.Atan2(toSubject.z, toSubject.x);
        Vector3 center = subjectFlat;
        float scanFloorY = subjectWorldPos.y;

        // Floor ring (64-segment circle)
        ringObj = new GameObject("ScanRing");
        LineRenderer lr = ringObj.AddComponent<LineRenderer>();
        lr.loop = true;
        lr.positionCount = 64;
        lr.startWidth = 0.02f;
        lr.endWidth = 0.02f;
        lr.material = CreateUnlitMaterial(new Color(1, 1, 1, 0.7f));
        for (int i = 0; i < 64; i++)
        {
            float angle = (i / 64f) * Mathf.PI * 2f;
            float x = center.x + Mathf.Cos(angle) * scanRadius;
            float z = center.z + Mathf.Sin(angle) * scanRadius;
            lr.SetPosition(i, new Vector3(x, scanFloorY, z));
        }

        // 30 capture dots
        captureDots.Clear();
        for (int i = 0; i < MaxFrames; i++)
        {
            float dotAngle = scanStartAngle + (i * DegreesPerCapture * Mathf.Deg2Rad);
            float x = center.x + Mathf.Cos(dotAngle) * scanRadius;
            float z = center.z + Mathf.Sin(dotAngle) * scanRadius;
            GameObject dot = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            dot.transform.position = new Vector3(x, scanFloorY + 0.05f, z);
            dot.transform.localScale = Vector3.one * 0.08f;
            dot.GetComponent<Renderer>().material = CreateUnlitMaterial(new Color(0.5f, 0.5f, 0.5f, 0.5f));
            Destroy(dot.GetComponent<Collider>());
            captureDots.Add(dot);
        }

        // Direction arrow
        directionArrow = GameObject.CreatePrimitive(PrimitiveType.Cube);
        directionArrow.transform.localScale = new Vector3(0.15f, 0.05f, 0.3f);
        directionArrow.GetComponent<Renderer>().material = CreateUnlitMaterial(new Color(0, 1, 0.3f, 0.9f));
        Destroy(directionArrow.GetComponent<Collider>());
        UpdateArrowPosition();
    }

    void UpdateArrowPosition()
    {
        if (directionArrow == null) return;

        Vector3 headFlat = new Vector3(headTransform.position.x, 0, headTransform.position.z);
        Vector3 subjectFlat = new Vector3(subjectWorldPos.x, 0, subjectWorldPos.z);
        // ⚠️ GAP — rest of body missing. From prose: places arrow on ring 30° ahead of user's
        //          current angle, oriented tangent (clockwise direction of revolve).
    }

    // =========================================================
    // HELPERS (RECOVERED)
    // =========================================================

    void SetStatus(string text, Color color)
    {
        Debug.Log($"[HoloBorn] {text}");
        // In actual build, updates a TextMeshProUGUI on the HUD canvas
    }

    Material CreateUnlitMaterial(Color color)
    {
        Material mat = new Material(Shader.Find("Sprites/Default"));
        mat.color = color;
        return mat;
    }
}

// =========================================================
// CERTIFICATE BYPASS (REQUIRED for ngrok HTTPS) — RECOVERED VERBATIM
// In the rebuild, MOVE THIS to Assets/HoloBorn/Scripts/BypassCertificate.cs
// for cleaner organization.
// =========================================================
public class BypassCertificate : CertificateHandler
{
    protected override bool ValidateCertificate(byte[] certificateData)
    {
        return true;
    }
}
