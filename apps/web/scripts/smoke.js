#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const requiredFiles = [
  "app/page.tsx",
  "app/market/page.tsx",
  "app/watchlist/page.tsx",
  "app/positions/page.tsx",
  "app/orders/page.tsx",
  "app/auth/page.tsx",
  "lib/api.ts"
];

const missing = requiredFiles.filter((file) => !fs.existsSync(path.join(root, file)));
if (missing.length > 0) {
  console.error("Missing required frontend route files:", missing.join(", "));
  process.exit(1);
}

const apiFile = fs.readFileSync(path.join(root, "lib/api.ts"), "utf8");
const requiredEndpoints = [
  "/health",
  "/market/quote",
  "/market/bars",
  "/watchlists/",
  "/positions/",
  "/orders/"
];

for (const endpoint of requiredEndpoints) {
  if (!apiFile.includes(endpoint)) {
    console.error(`API wiring check failed: missing ${endpoint}`);
    process.exit(1);
  }
}

console.log("Frontend smoke passed: routes and API wiring are present.");
