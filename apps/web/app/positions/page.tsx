import { getPositions } from "../../lib/api";

const DEMO_USER = "demo-user";

export default async function PositionsPage() {
  let data: Awaited<ReturnType<typeof getPositions>> | null = null;
  let error = "";

  try {
    data = await getPositions(DEMO_USER);
  } catch (err) {
    error = err instanceof Error ? err.message : "Positions unavailable";
  }

  return (
    <section className="card">
      <h1>Positions</h1>
      {data ? (
        data.positions.map((position) => (
          <div key={position.symbol} className="kv">
            <span>{position.symbol} ({position.quantity})</span>
            <strong>${position.market_price.toFixed(2)}</strong>
          </div>
        ))
      ) : (
        <p className="error">{error}</p>
      )}
    </section>
  );
}
