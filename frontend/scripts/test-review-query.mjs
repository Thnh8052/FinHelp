// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// The admin review page: the request it sends for its filters, and the tone of each problem label (src/features/admin/reviewQuery.ts).
//
//   node scripts/test-review-query.mjs
import assert from "node:assert/strict";
import { flaggedPagesText, labelTone, reviewPath } from "../src/features/admin/reviewQuery.ts";

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

check("everyone, every problem, open: only the window", () => assert.equal(reviewPath({ days: 14, user: "", label: "", status: "open" }), "/auth/admin/review?days=14&status=open"));
check("one user, one problem, reviewed", () =>
  assert.equal(reviewPath({ days: 30, user: "usr_1", label: "not_found", status: "reviewed" }), "/auth/admin/review?days=30&status=reviewed&label=not_found&user=usr_1"));
check("the guests filter is sent as it is", () => assert.equal(reviewPath({ days: 7, user: "guests", label: "", status: "all" }), "/auth/admin/review?days=7&status=all&user=guests"));
check("a user id is escaped", () => assert.match(reviewPath({ days: 7, user: "a&b", label: "", status: "open" }), /user=a%26b$/));
check("what the user reported or what was blocked is red; a warning or a partial answer amber; the rest neutral", () => {
  assert.deepEqual(["user_report", "blocked"].map(labelTone), ["negative", "negative"]);
  assert.deepEqual(["not_traced", "partial", "not_found", "refused", "degraded", "slow"].map(labelTone), ["warn", "warn", "warn", "warn", "neutral", "neutral"]);
  assert.equal(labelTone("safety"), "neutral");
  assert.equal(labelTone("guard_sample"), "neutral"); // a sample to look at, not a problem
});

check("each flagged page is named by its file and page, with its problems; a deleted document says so", () => {
  const words = { pageOf: "{file} tr. {page}", deletedDocument: "tài liệu đã xóa",
    pageFlags: { may_be_misread: "bảng có thể đọc sai", read_from_image: "nhận dạng từ ảnh", from_figure: "số lấy từ hình/biểu đồ", picture_unread: "có hình chưa đọc được" } };
  assert.equal(flaggedPagesText([{ document_id: "d1", page: 50, flags: ["may_be_misread", "from_figure"], file_name: "FinStats.pdf" },
                                 { document_id: "dx", page: 3, flags: ["read_from_image"], file_name: null }], words),
    "FinStats.pdf tr. 50 (bảng có thể đọc sai, số lấy từ hình/biểu đồ) · tài liệu đã xóa tr. 3 (nhận dạng từ ảnh)");
  assert.equal(flaggedPagesText([], words), "");
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
