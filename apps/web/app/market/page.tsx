import { getBars, getQuote } from "../../lib/api";

const SYMBOL = "AAPL";

export default async function MarketPage() {
  let quoteError = "";
  let barsError = "";
  let quote: Awaited<ReturnType<typeof getQuote>> | null = null;
  let bars: Awaited<ReturnType<typeof getBars>> | null = null;

  try {
    quote = await getQuote(SYMBOL);
  } catch (err) {
    quoteError = err instanceof Error ? err.message : "Quote unavailable";
  }

  try {
    bars = await getBars(SYMBOL);
  } catch (err) {
    barsError = err instanceof Error ? err.message : "Bars unavailable";
  }

  return (
    <section className="grid">
      <article className="card">
        <h1>Market Data</h1>
        <p className="muted">Default symbol: {SYMBOL}</p>
        {quote ? (
          <>
            <p className="kv"><span>Price</span><strong>${quote.price.toFixed(2)}</strong></p>
            <p className="kv"><span>As of</span><strong>{quote.as_of}</strong></p>
            <p className="kv"><span>Mode</span><strong>{quote.provider_mode}</strong></p>
          </>
        ) : (
          <p className="error">{quoteError}</p>
        )}
      </article>
      <article className="card">
        <h2>Recent Bars</h2>
        {bars ? (
          bars.bars.slice(-5).map((bar) => (
            <p className="kv" key={bar.time}>
              <span>{bar.time.slice(0, 10)}</span>
              <strong>{bar.close.toFixed(2)}</strong>
            </p>
          ))
        ) : (
          <p className="error">{barsError}</p>
        )}
      </article>
    </section>
  );
}
