import { getWatchlist } from "../../lib/api";

const DEMO_USER = "demo-user";

export default async function WatchlistPage() {
  let data: Awaited<ReturnType<typeof getWatchlist>> | null = null;
  let error = "";

  try {
    data = await getWatchlist(DEMO_USER);
  } catch (err) {
    error = err instanceof Error ? err.message : "Watchlist unavailable";
  }

  return (
    <section className="card">
      <h1>Watchlist</h1>
      <p className="muted">User context: {DEMO_USER}</p>
      {data ? (
        <>
          <p className="kv"><span>Provider mode</span><strong>{data.provider_mode}</strong></p>
          {data.symbols.length ? (
            data.symbols.map((symbol) => <p className="kv" key={symbol}><span>Symbol</span><strong>{symbol}</strong></p>)
          ) : (
            <p className="muted">No symbols yet. Add via backend `POST /watchlists/{'{user_id}'}`.</p>
          )}
        </>
      ) : (
        <p className="error">{error}</p>
      )}
    </section>
  );
}
