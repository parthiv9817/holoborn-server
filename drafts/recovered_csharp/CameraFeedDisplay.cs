// SOURCE: Recovered verbatim from web chat 2026-05-05 (originally written ~April 2026)
// STATUS: FULL — likely close to shipped version (thin script, low change surface)
// NOTES: HEADSET_CAMERA permission request happens here. Wires PassthroughCameraAccess
//        (Meta MRUK component) texture to a HUD RawImage every Update.

using UnityEngine;
using UnityEngine.UI;

public class CameraFeedDisplay : MonoBehaviour
{
    public RawImage displayImage;
    private PassthroughCameraAccess cameraAccess;
    private bool permissionRequested = false;

    void Start()
    {
        cameraAccess = FindFirstObjectByType<PassthroughCameraAccess>();

        if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(
            "horizonos.permission.HEADSET_CAMERA"))
        {
            UnityEngine.Android.Permission.RequestUserPermission(
                "horizonos.permission.HEADSET_CAMERA");
            permissionRequested = true;
        }
    }

    void Update()
    {
        if (cameraAccess != null && cameraAccess.IsPlaying)
        {
            Texture tex = cameraAccess.GetTexture();
            if (tex != null)
                displayImage.texture = tex;
        }
    }
}
