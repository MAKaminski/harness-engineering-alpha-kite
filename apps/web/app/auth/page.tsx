export default function AuthPage() {
  return (
    <section className="card">
      <h1>Authentication</h1>
      <p>
        Auth is handled via backend session APIs and Supabase-backed user context.
        Use `POST /auth/session` to mint a session token, then `GET /auth/session/{'{token}'}`
        for retrieval.
      </p>
      <p className="muted">
        In mock mode, sessions are stored in in-memory backend state.
      </p>
    </section>
  );
}
