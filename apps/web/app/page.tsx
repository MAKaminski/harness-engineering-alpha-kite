import { getHealth } from "../lib/api";

export default async function HomePage() {
  let health: { status: string; providers: Record<string, string> } | null = null;
  let error = "";

  try {
    health = await getHealth();
  } catch (err) {
    error = err instanceof Error ? err.message : "Unable to reach backend";
  }

  return (
    <section className="grid">
      <article className="card">
        <h1>Alpha-Kite Trading UI</h1>
        <p className="muted">
          Frontend deployed on Vercel, API on Railway/FastAPI, data from Polygon,
          Schwab, Supabase, and Camelot ingestion.
        </p>
        {error ? <p className="error">{error}</p> : null}
      </article>
      <article className="card">
        <h2>Backend Health</h2>
        {health ? (
          <>
            <p className="kv"><span>Status</span><strong>{health.status}</strong></p>
            {Object.entries(health.providers).map(([provider, mode]) => (
              <p className="kv" key={provider}>
                <span>{provider}</span>
                <strong>{mode}</strong>
              </p>
            ))}
          </>
        ) : (
          <p className="muted">Run API (`python3 apps/api/main.py`) and set `NEXT_PUBLIC_API_BASE_URL`.</p>
        )}
      </article>
    </section>
  );
}
