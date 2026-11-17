// No imports and no DOM, so the node tests run this file directly. Erasable TypeScript only.
export function statusText(ok: boolean, body: unknown): string {
  const healthy = ok && typeof body === "object" && body !== null && (body as { status?: unknown }).status === "ok";
  return healthy ? "API: ok" : "API: unavailable";
}
