import { getOrders } from "../../lib/api";

const DEMO_USER = "demo-user";

export default async function OrdersPage() {
  let data: Awaited<ReturnType<typeof getOrders>> | null = null;
  let error = "";

  try {
    data = await getOrders(DEMO_USER);
  } catch (err) {
    error = err instanceof Error ? err.message : "Orders unavailable";
  }

  return (
    <section className="card">
      <h1>Orders</h1>
      {data ? (
        data.orders.map((order) => (
          <div key={order.id} className="kv">
            <span>{order.symbol} {order.side} {order.quantity}</span>
            <strong>{order.status}</strong>
          </div>
        ))
      ) : (
        <p className="error">{error}</p>
      )}
    </section>
  );
}
