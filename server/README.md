# socialverify-server

Backend API service for SocialVerify, providing user authentication, investigation history persistence, real-time pipeline monitoring, PDF generation, and proxy interfaces to news and social collectors.

## Installation

```bash
bun install
```

## Running the Server

```bash
bun run src/index.ts
```

## Monitoring API

Provides live metrics and scenario execution history for the workspace Monitoring tab:

```http
GET /api/monitoring?mode=live
```

Query Parameters:
- `mode`: `"live"` (default) reads real saved conversations and messages from the local store / PostgreSQL DB; `"mock"` streams benchmark fixture data.

Returns:
- System operational status and active workflows.
- Aggregate KPIs: total research workflows, completion/failure rates, news/social counts, and average latency.
- Agent pipeline stage performance metrics.
- Scenario-level execution records and trace logs.

## Social Search API

Authenticated clients can fetch normalized posts from Reddit, Bluesky, and Mastodon. Bluesky uses its public XRPC search endpoint; Mastodon and Reddit retain their existing providers. Each record keeps its original publication time when supplied and a separate retrieval time. Missing publication times remain `null`; provider failures and rate limits are reported in `data.errors`.

```http
POST /api/social/search
Content-Type: application/json

{
  "topics": ["climate policy", "renewable energy"],
  "platforms": ["reddit", "bluesky", "mastodon"],
  "limit": 10
}
```

`platforms` and `limit` are optional. Reddit requires the credentials documented in `.env.example`; Bluesky and Mastodon do not require API keys. Source failures are returned in `data.errors` without discarding successful posts from other sources.

## Structured Investigation Data

The Python investigation service searches a configurable window (`INVESTIGATION_WINDOW_DAYS`, default 30; allowed range 1-365), requests date-bounded news results, and calculates spread from the publication timestamps available from each provider. Social search providers do not guarantee historical completeness; returned records outside the window are excluded from its timeline, and missing timestamps are reported rather than guessed.

Authenticated clients can retrieve the latest investigation's validated source records, earliest source found, coverage and time series with:

```http
GET /api/conversation/investigation/{conversationId}
```

The endpoint enforces conversation ownership. Structured results are retained with the existing bot report message, so both PostgreSQL and the configured local-store fallback preserve them without changing the existing frontend conversation layout.
