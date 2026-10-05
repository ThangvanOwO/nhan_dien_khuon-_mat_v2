const {test} = require("node:test");
const assert = require("node:assert/strict");
const policy = require("../static/js/camera-policy.js");
const camera = (deviceId, label) => ({kind: "videoinput", deviceId, label});
const laptop = camera("acer", "ACER HD User Facing");
const iriun = camera("iriun", "Iriun Webcam");
const usb = camera("usb", "Logitech USB Webcam");

test("prefers laptop even when Iriun is first/default", () => {
    assert.equal(policy.choose([iriun, usb, laptop]).deviceId, "acer");
});
test("does not silently open a virtual camera", () => {
    assert.equal(policy.choose([iriun]), null);
});
test("does not restore a saved virtual camera automatically", () => {
    assert.equal(policy.choose([iriun, laptop], "iriun").deviceId, "acer");
});
test("remembers an available physical camera selected by the user", () => {
    assert.equal(policy.choose([laptop, usb], "usb").deviceId, "usb");
});
test("missing saved device falls back to built-in, not virtual", () => {
    assert.equal(policy.choose([iriun, laptop], "gone").deviceId, "acer");
});
test("manual selection can explicitly choose a virtual camera", () => {
    assert.equal(policy.choose([iriun, laptop], "", "iriun").deviceId, "iriun");
});
test("missing explicit device does not silently switch to another camera", () => {
    assert.equal(policy.choose([laptop], "", "gone"), null);
});
test("hidden labels require permission, not guessing device order", () => {
    assert.equal(policy.choose([camera("first", ""), camera("second", "")]), null);
});
test("ignores microphones and devices without an id", () => {
    assert.equal(policy.choose([{kind: "audioinput", deviceId: "mic", label: "Acer"}, camera("", "ACER")]), null);
});
test("uses exact deviceId and never records microphone audio", () => {
    assert.deepEqual(policy.constraints(laptop), {video: {deviceId: {exact: "acer"}, width: {ideal: 1280}, height: {ideal: 720}}, audio: false});
    assert.throws(() => policy.constraints(null));
});
test("recognizes virtual and built-in labels without case sensitivity", () => {
    for (const label of ["IRIUN Webcam", "OBS Virtual Camera", "DroidCam", "NVIDIA Broadcast"]) assert.equal(policy.isVirtual({label}), true);
    for (const label of ["ACER HD User Facing", "Integrated Webcam", "FaceTime HD Camera", "Built-in Camera"]) assert.equal(policy.isBuiltIn({label}), true);
});
