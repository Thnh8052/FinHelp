// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// What the sign-up form refuses before it sends anything, field by field, so each message shows under its own field in the app's language
// (the browser's own tooltips were in the browser's language: "Please match the requested format" over a Vietnamese page). The server checks
// the same rules again (backend auth.RegisterRequest).
//
//   node scripts/test-sign-up.mjs
import assert from "node:assert/strict";
import { passwordChecks, signUpProblems } from "../src/components/auth/signUpRules.ts";

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
const ok = { email: "lan@example.com", username: "lan.nguyen_1", password: "longenough1" };

check("a valid form has no problem", () => assert.deepEqual(signUpProblems(ok), {}));
check("every field is required", () =>
  assert.deepEqual(signUpProblems({ email: "", username: "", password: "" }), { email: "emailMissing", username: "usernameMissing", password: "passwordMissing" }));
check("an address without @ or domain is refused", () => {
  for (const email of ["lan", "lan@", "lan@example", "lan @example.com"]) assert.equal(signUpProblems({ ...ok, email }).email, "emailInvalid", email);
});
check("the username follows the server's rule (3-32: letters, digits, . _ -)", () => {
  for (const username of ["ab", "lan nguyen", "lân", "a".repeat(33)]) assert.equal(signUpProblems({ ...ok, username }).username, "usernameRule", username);
  for (const username of ["abc", "a.b-c_d", "A".repeat(32)]) assert.equal(signUpProblems({ ...ok, username }).username, undefined, username);
});
check("spaces around the username or the address are not an error (they are trimmed when sent)", () =>
  assert.deepEqual(signUpProblems({ ...ok, email: " lan@example.com ", username: " lan " }), {}));
check("a password under 8 characters is too short", () => assert.equal(signUpProblems({ ...ok, password: "short12" }).password, "passwordShort"));
check("the live password checklist", () => {
  assert.deepEqual(passwordChecks(""), { length: false });
  assert.deepEqual(passwordChecks("12345678"), { length: true });
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
