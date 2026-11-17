import test from "node:test";
import assert from "node:assert/strict";
import { drainQueue } from "../src/offline.mjs";
const item = (id, account = 1, error = "") => ({
  id,
  account,
  error,
  data: { otp: "123456", proof_photo: { uri: "file:///persistent/photo.jpg" } },
});
const run = async (items, send, overrides = {}) => {
  const removed = [],
    failed = [];
  await drainQueue({
    items,
    account: 1,
    send,
    remove: async (i) => removed.push(i.id),
    fail: async (i, e) => failed.push([i.id, e.message]),
    isNetworkError: (e) => e.status === 0,
    isCurrent: () => true,
    ...overrides,
  });
  return { removed, failed };
};
test("only current account captures synchronize", async () => {
  const sent = [];
  const result = await run([item("other", 2), item("mine")], async (i) =>
    sent.push(i.id),
  );
  assert.deepEqual(sent, ["mine"]);
  assert.deepEqual(result.removed, ["mine"]);
});
test("network failure retains the capture and stops the batch", async () => {
  const result = await run([item("first"), item("next")], async () => {
    throw Object.assign(new Error("offline"), { status: 0 });
  });
  assert.deepEqual(result, { removed: [], failed: [] });
});
test("validation failure records error without removing proof", async () => {
  const result = await run([item("expired"), item("next")], async () => {
    throw Object.assign(new Error("Expired code"), { status: 400 });
  });
  assert.deepEqual(result, {
    removed: [],
    failed: [["expired", "Expired code"]],
  });
});
test("a lost response retries the same key and exact persisted payload", async () => {
  const capture = item("stable-key");
  let first = true;
  const observed = [];
  const send = async (i) => {
    observed.push(structuredClone(i));
    if (first) {
      first = false;
      throw Object.assign(new Error("response lost"), { status: 0 });
    }
  };
  await run([capture], send);
  const result = await run([JSON.parse(JSON.stringify(capture))], send);
  assert.deepEqual(observed[0], observed[1]);
  assert.deepEqual(result.removed, ["stable-key"]);
});
test("failed captures await explicit retry", async () => {
  const sent = [];
  await run([item("failed", 1, "Rejected"), item("ready")], async (i) =>
    sent.push(i.id),
  );
  assert.deepEqual(sent, ["ready"]);
});
test("switching accounts stops subsequent submissions", async () => {
  let current = true;
  const sent = [];
  await run(
    [item("first"), item("second")],
    async (i) => {
      sent.push(i.id);
      current = false;
    },
    { isCurrent: () => current },
  );
  assert.deepEqual(sent, ["first"]);
});
test("authorization errors remain visible instead of network retries", async () => {
  const result = await run([item("denied")], async () => {
    throw Object.assign(new Error("Permission denied"), { status: 403 });
  });
  assert.deepEqual(result.failed, [["denied", "Permission denied"]]);
});
