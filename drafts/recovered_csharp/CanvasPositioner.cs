// SOURCE: Recovered verbatim from web chat 2026-05-05 (originally written ~April 2026)
// STATUS: FULL — separate script from TagAlongCanvas (not merged)
// NOTES: Thumbstick fine-tune of HUD canvas position + scale. Used during testing
//        to find comfortable HUD placement. Left stick X/Y = local X/Y nudge,
//        right stick Y = depth (Z), right stick X = scale.

using UnityEngine;
using UnityEngine.InputSystem;

public class CanvasPositioner : MonoBehaviour
{
    public float moveSpeed = 0.001f;

    private InputAction thumbstick;
    private InputAction secondaryThumbstick;

    void Start()
    {
        thumbstick = new InputAction("LeftThumbstick", InputActionType.Value);
        thumbstick.AddBinding("<XRController>{LeftHand}/thumbstick");
        thumbstick.Enable();

        secondaryThumbstick = new InputAction("RightThumbstick", InputActionType.Value);
        secondaryThumbstick.AddBinding("<XRController>{RightHand}/thumbstick");
        secondaryThumbstick.Enable();
    }

    void Update()
    {
        Vector2 left = thumbstick.ReadValue<Vector2>();
        Vector2 right = secondaryThumbstick.ReadValue<Vector2>();

        // Left stick: move X and Y
        transform.localPosition += new Vector3(
            left.x * moveSpeed, left.y * moveSpeed, 0);

        // Right stick Y: move Z (closer/further)
        transform.localPosition += new Vector3(0, 0, right.y * moveSpeed);

        // Right stick X: scale up/down
        float scaleChange = right.x * 0.00001f;
        transform.localScale += new Vector3(scaleChange, scaleChange, scaleChange);
    }
}
