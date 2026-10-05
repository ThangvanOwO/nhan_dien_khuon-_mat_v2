/* Prefer a built-in webcam, never silently fall back to a virtual camera. */
(function (root) {
    "use strict";
    function isVirtual(camera) {
        return /iriun|virtual|obs|droidcam|epoccam|manycam|snap camera|nvidia broadcast|camo|splitcam|ndi/i.test(camera.label || "");
    }
    function isBuiltIn(camera) {
        return /integrated|built[ -]?in|user[ -]?facing|facetime|easycamera|acer hd|hp wide vision|hp widevision/i.test(camera.label || "");
    }
    function choose(devices, savedId, explicitId) {
        const cameras = devices.filter(device => device.kind === "videoinput" && device.deviceId);
        // A virtual camera is allowed only when explicitly chosen in this page.
        if (explicitId) return cameras.find(camera => camera.deviceId === explicitId) || null;
        const physical = cameras.filter(camera => camera.label && !isVirtual(camera));
        return physical.find(camera => camera.deviceId === savedId)
            || physical.find(isBuiltIn) || physical[0] || null;
    }
    function constraints(camera) {
        if (!camera || !camera.deviceId) throw new Error("Chưa chọn được webcam laptop.");
        return {video: {deviceId: {exact: camera.deviceId}, width: {ideal: 1280}, height: {ideal: 720}}, audio: false};
    }
    const policy = Object.freeze({isVirtual, isBuiltIn, choose, constraints});
    if (typeof module === "object" && module.exports) module.exports = policy;
    else root.VistaCameraPolicy = policy;
})(typeof globalThis !== "undefined" ? globalThis : this);
