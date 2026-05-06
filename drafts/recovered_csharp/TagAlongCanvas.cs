// SOURCE: Recovered verbatim from web chat 2026-05-05 (originally written ~April 2026)
// STATUS: FULL — referenced in chat as "unchanged" through the TRELLIS pivot, likely shipped
// NOTES: Lazy-follow HUD. Lerp position toward target (head + offset basis), Lerp rotation
//        to match head orientation. SEPARATE script from CanvasPositioner.

using UnityEngine;

public class TagAlongCanvas : MonoBehaviour
{
    public Transform headTransform;
    public Vector3 offset = new Vector3(-0.3f, -0.1f, 1.0f);
    public float followSpeed = 2.0f;

    void Update()
    {
        if (headTransform == null) return;

        Vector3 targetPos = headTransform.position
            + headTransform.forward * offset.z
            + headTransform.right * offset.x
            + headTransform.up * offset.y;

        transform.position = Vector3.Lerp(
            transform.position, targetPos, Time.deltaTime * followSpeed);
        transform.rotation = Quaternion.Lerp(
            transform.rotation, headTransform.rotation, Time.deltaTime * followSpeed);
    }
}
