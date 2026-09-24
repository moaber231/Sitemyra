// Lightweight liveness probe for the frontend container (used by
// docker-compose.prod.yml healthchecks and platform routers).
// Kept dynamic so it reflects a running server, not a build-time artifact.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  return Response.json({ status: "ok" });
}
