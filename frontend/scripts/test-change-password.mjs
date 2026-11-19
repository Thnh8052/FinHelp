// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// What the change-password dialog refuses before it sends anything (src/components/auth/passwordChange.ts). The server checks the current password
// and the 8-character minimum again; these rules only spare a request whose answer is known.
//
//   node scripts/test-change-password.mjs
import assert from "node:assert/strict";
import { MIN_PASSWORD, passwordChangeProblem } from "../src/components/auth/passwordChange.ts";

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

check("the minimum is the server's (PASSWORD_MIN_CHARS = 8)", () => assert.equal(MIN_PASSWORD, 8));
check("a valid change has no problem", () => assert.equal(passwordChangeProblem("old-pass-1", "new-pass-22", "new-pass-22"), null));
check("the current password is required", () => assert.equal(passwordChangeProblem("", "new-pass-22", "new-pass-22"), "currentMissing"));
check("a new password under 8 characters is too short", () => assert.equal(passwordChangeProblem("old-pass-1", "short1", "short1"), "tooShort"));
check("the two new passwords must match", () => assert.equal(passwordChangeProblem("old-pass-1", "new-pass-22", "new-pass-23"), "mismatch"));
check("the new password must differ from the current one", () => assert.equal(passwordChangeProblem("same-pass-1", "same-pass-1", "same-pass-1"), "unchanged"));
check("spaces count as typed (no trimming of passwords)", () => assert.equal(passwordChangeProblem("old-pass-1", "new-pass-22 ", "new-pass-22"), "mismatch"));

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
