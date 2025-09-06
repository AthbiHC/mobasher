# Mobasher API (Phase 1)

Base URL (dev): `http://127.0.0.1:8001`

## Health
- GET `/health` → `{ "status": "ok" }`

## Channels
- GET `/channels?limit=100&offset=0&active_only=false`
  - Response:
```json
{
  "items": [ { "id": "kuwait_news", "name": "..." } ],
  "meta": { "limit": 100, "offset": 0, "next_offset": null }
}
```
- GET `/channels/{id}` → channel
- POST `/channels` (upsert)
```json
{ "id": "kuwait_news", "name": "Kuwait News", "url": "...", "headers": {}, "active": true }
```

## Recordings
- GET `/recordings?channel_id=&since=&status=&limit=50&offset=0`
  - `status`: running|completed|failed|stopped
  - Response is paginated with `items[]` and `meta{...}`

## Segments
- GET `/segments?channel_id=&start=&end=&status=&limit=200&offset=0`
  - `status`: created|processing|completed|failed
  - Response is paginated with `items[]` and `meta{...}`

## Transcripts
- GET `/transcripts?channel_id=&since=&limit=100&offset=0`
  - Returns pairs of `segment` and `transcript` with pagination meta
  - Example:
```json
{
  "items": [
    {
      "segment": { "id": "...", "channel_id": "...", "started_at": "..." },
      "transcript": { "language": "ar", "text": "...", "confidence": -0.16, "model_name": "medium" }
    }
  ],
  "meta": { "limit": 100, "offset": 0, "next_offset": null }
}
```
Notes
- API is bound to localhost by default via CLI: `./scripts/mediaview api serve`
- Use `--public` to bind 0.0.0.0 (not recommended without network protection)
