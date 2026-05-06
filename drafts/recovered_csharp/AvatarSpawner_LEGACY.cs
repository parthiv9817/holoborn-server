// SOURCE: Recovered from web chat 2026-05-05 (April 28 doc)
// STATUS: PARTIAL — LEGACY single-shot version. Pre-burst capture, pre-Zoro-rewrite.
//         The AvatarSpawner shipped in the production APK is NOT this version.
// USE: Architectural reference for the GLB-load + spawn pattern only. The
//      single-shot capture path is replaced by ScanController.UploadAndSpawn in shipped.
// NOTES: ScanController.Start() disables this script at runtime in the shipped build
//        (button conflict — both wanted A button). In the rebuild, decide whether
//        to keep AvatarSpawner at all or fold its glTFast spawn helper into ScanController.

using System.Collections;
using UnityEngine;
using UnityEngine.Networking;
using GLTFast;

public class AvatarSpawner : MonoBehaviour
{
    public string serverUrl = "https://YOUR-NGROK-URL.ngrok-free.app";
    public Transform headTransform;

    private PassthroughCameraAccess cameraAccess;
    private bool isGenerating = false;

    void Start()
    {
        cameraAccess = FindFirstObjectByType<PassthroughCameraAccess>();
    }

    public void TriggerGeneration()
    {
        if (!isGenerating)
            StartCoroutine(CaptureAndGenerate());
    }

    IEnumerator CaptureAndGenerate()
    {
        isGenerating = true;

        // Capture frame (same pattern ScanController uses)
        Texture srcTex = cameraAccess.GetTexture();
        RenderTexture rt = RenderTexture.GetTemporary(
            srcTex.width, srcTex.height, 0, RenderTextureFormat.ARGB32);
        Graphics.Blit(srcTex, rt);
        RenderTexture.active = rt;
        Texture2D tex2D = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
        tex2D.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tex2D.Apply();
        RenderTexture.ReleaseTemporary(rt);
        byte[] jpegBytes = tex2D.EncodeToJPG(75);
        Destroy(tex2D);

        // POST /generate (LEGACY endpoint — shipped uses /generate-multiview)
        using (UnityWebRequest req = new UnityWebRequest(serverUrl + "/generate", "POST"))
        {
            req.uploadHandler = new UploadHandlerRaw(jpegBytes);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "image/jpeg");
            req.certificateHandler = new BypassCertificate();

            yield return req.SendWebRequest();

            var response = JsonUtility.FromJson<GenerateResponse>(req.downloadHandler.text);

            if (response.status == "bad_framing" || response.status != "processing")
            {
                isGenerating = false;
                yield break;
            }

            // Poll loop — pattern useful for ScanController.PollAndDownloadGLB rebuild
            string taskId = response.task_id;
            while (true)
            {
                yield return new WaitForSeconds(3f);
                using (UnityWebRequest poll = UnityWebRequest.Get(
                    serverUrl + "/generate/" + taskId + "/status"))
                {
                    poll.certificateHandler = new BypassCertificate();
                    yield return poll.SendWebRequest();

                    var status = JsonUtility.FromJson<StatusResponse>(poll.downloadHandler.text);

                    if (status.status == "complete")
                    {
                        string glbUrl = serverUrl + status.glb_url;
                        using (UnityWebRequest dl = UnityWebRequest.Get(glbUrl))
                        {
                            dl.certificateHandler = new BypassCertificate();
                            yield return dl.SendWebRequest();
                            LoadAndInstantiateGLB(dl.downloadHandler.data);
                        }
                        break;
                    }
                    else if (status.status == "failed") break;
                }
            }
        }
        isGenerating = false;
    }

    [System.Serializable] private class GenerateResponse { public string status; public string task_id; }
    [System.Serializable] private class StatusResponse { public string status; public int progress; public string glb_url; }

    // ★★★ THIS IS THE KEY HELPER — port to ScanController.LoadAndInstantiateGLB / SpawnGLBFromBytes ★★★
    async void LoadAndInstantiateGLB(byte[] glbData)
    {
        var gltf = new GltfImport();
        bool success = await gltf.LoadGltfBinary(glbData);
        if (!success) return;

        GameObject avatar = new GameObject("GeneratedAvatar");
        Vector3 spawnPos = headTransform.position + headTransform.forward * 1.5f;
        spawnPos.y = 0f;
        avatar.transform.position = spawnPos;

        Vector3 lookDir = headTransform.position - spawnPos;
        lookDir.y = 0f;
        if (lookDir.sqrMagnitude > 0.001f)
            avatar.transform.rotation = Quaternion.LookRotation(lookDir);

        await gltf.InstantiateMainSceneAsync(avatar.transform);

        // ⚠️ GAP — shipped version per chat fragments includes:
        //         - Auto-scale to 1.7m based on bounds.size.y
        //         - Floor-align via bounds.min.y offset
        //         - Shader fallback for stripped URP materials (swap to URP/Lit)
        //         - Texture recovery from glTFast texture array
    }
}
