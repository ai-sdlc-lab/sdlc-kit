// Built-in node:test only; Node strips the types of status.ts. Inside describe() so the JUnit report has a
// <testsuite> for the merge in `make ci-test`.
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { statusText } from "../src/status.ts";

describe("status", () => {
  test("test_status_ok_only_for_healthy_body", () => {
    assert.equal(statusText(true, { status: "ok" }), "API: ok");
    for (const [ok, body] of [[false, { status: "ok" }], [true, null], [true, { status: "<b>x</b>" }], [true, "ok"]]) {
      assert.equal(statusText(ok, body), "API: unavailable");
    }
  });
});
