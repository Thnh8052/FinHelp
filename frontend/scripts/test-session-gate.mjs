// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// When the app waits for the session check instead of drawing the chat (src/context/sessionGate.ts). Auth flow test 19/11: the profile request had
// failed with a server error (500 while the backend started), so the browser kept its session flag with no user; a sign-up that the server refused
// then hid the whole chat while it ran, the sign-in box with it, and the refusal was never shown.
//
//   node scripts/test-session-gate.mjs
import assert from "node:assert/strict";
import { waitsForSession } from "../src/context/sessionGate.ts";

let failed = 0;
const check = (name, fn) => {
  try {
    fn();
    console.log("PASS ", name);
  } catch (e) {
    failed++;
    console.log("FAIL ", name, "\n      ", e.message.split("\n")[0]);
  }
};

const member = { user_id: "usr_1" };

check("the first check of a kept session hides the chat (a member would look like a guest)", () => {
  assert.equal(waitsForSession({ hasSession: true, user: null, checkingSession: true }), true);
});
check("a sign-in or sign-up running in a guest view with a kept session does not hide the chat", () => {
  assert.equal(waitsForSession({ hasSession: true, user: null, checkingSession: false }), false);
});
check("a guest without a session never waits", () => {
  assert.equal(waitsForSession({ hasSession: false, user: null, checkingSession: true }), false);
});
check("a signed-in member never waits", () => {
  assert.equal(waitsForSession({ hasSession: true, user: member, checkingSession: true }), false);
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
