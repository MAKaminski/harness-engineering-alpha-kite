import Link from "next/link";

const routes = [
  ["/", "Overview"],
  ["/market", "Market"],
  ["/watchlist", "Watchlist"],
  ["/positions", "Positions"],
  ["/orders", "Orders"],
  ["/auth", "Auth"]
] as const;

export default function Nav() {
  return (
    <nav className="nav" aria-label="Main navigation">
      {routes.map(([href, label]) => (
        <Link key={href} href={href}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
