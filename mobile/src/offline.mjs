// Platform-independent queue policy, exercised by node:test with real failure sequences.
export async function drainQueue({
  items,
  account,
  send,
  remove,
  fail,
  isNetworkError,
  isCurrent,
}) {
  for (const item of items) {
    if (!isCurrent() || item.account !== account || item.error) continue;
    try {
      await send(item);
      await remove(item);
    } catch (error) {
      if (!isNetworkError(error)) await fail(item, error);
      break;
    }
  }
}
