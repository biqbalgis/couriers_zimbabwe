export interface QueuePolicyItem {
  account: number;
  error: string;
}
export function drainQueue<T extends QueuePolicyItem>(options: {
  items: T[];
  account: number;
  send: (item: T) => Promise<unknown>;
  remove: (item: T) => Promise<void>;
  fail: (item: T, error: unknown) => Promise<void>;
  isNetworkError: (error: unknown) => boolean;
  isCurrent: () => boolean;
}): Promise<void>;
