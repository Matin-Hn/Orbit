# Video Upload & Delivery Flow – Production Architecture

## 1. Frontend: Prepare & Request Upload URL

- User selects a video file via `<input type="file">`.
- Frontend calls `POST /api/videos/upload-request` with file metadata (name, size, MIME type).
- Backend validates user permissions and generates a **pre‑signed POST URL** (or multipart upload ID) from S3, valid for 60 seconds.

## 2. Direct Upload to S3 (No API Proxy)

- Frontend uploads video directly to the S3 pre‑signed URL using `fetch` or a resumable upload library.
- Upload is performed **chunked** (multipart) for large files (>5 MB) to handle interruptions.
- On success, S3 returns an ETag and the final object key.

## 3. Backend: Database Model Update & Async Processing

- Frontend notifies backend with `POST /api/videos/complete` containing the S3 key and ETag.
- Backend:
  - Creates a `Video` record in the database with status = `processing`.
  - Stores S3 URI, user ID, original filename, size, MIME type.
  - Triggers an **asynchronous job** (SQS / Bull / RabbitMQ) to transcode the video.
- Returns `202 Accepted` with video ID to frontend.

## 4. Transcoding & Thumbnail Generation (Background Job)

- Worker picks up the job:
  - Downloads the original video from S3 (or uses S3 event trigger).
  - Transcodes to HLS (`.m3u8` + `.ts` segments) or DASH for adaptive bitrate in several qualities.
  - Generates thumbnail sprites (for timeline preview) and a poster image.
  - Uploads all derivatives to a **different S3 bucket** (or same bucket with `processed/` prefix).
- Worker updates the database:
  - `status` → `ready`
  - Stores paths to HLS manifest, thumbnails, and metadata (duration, resolution, bitrate).
  - Optionally triggers a CDN invalidation (if using a CDN with cache).


## 5. Real-Time Status via WebSocket

- After upload completes (202 Accepted), frontend sends a WebSocket subscription for video:{id}.
- Worker finishes transcoding → backend pushes { type: "video.ready", videoId } to subscribed clients.
- Frontend receives event → fetches signed manifest URL → loads player.

---

## 6. Secure Playback via Manifest-Only Signed URLs

- User clicks "Play". Frontend calls `GET /api/videos/{id}/signed-url`.
- Backend verifies user access rights (e.g., subscription plan, ownership).
- Generates an S3/CloudFront **signed URL for the `.m3u8` manifest only**, valid for a short window (e.g., 15–60 seconds — just enough to start fetching).
- The manifest itself references publicly accessible `.ts` segment URLs (no signing on segments).
- Backend returns the signed manifest URL to the frontend.

### Why this works safely:
- **Manifest URL is short-lived** — an attacker can't share a lasting link.
- **Segments are public but useless alone** — without the manifest, a `.ts` file is just a random chunk of video with no play order, timing, or context.
- **No playback interruption** — once the player loads the manifest, segment fetching continues without re-authentication. The manifest signature only needs to be valid at fetch time, not for the full video duration.
- **Optional hardening**: Use **obfuscated/randomized segment paths** (e.g., UUID-based prefixes) so segments can't be guessed or enumerated.

---

## 7. Frontend Player & CDN Delivery (Unchanged)

- Frontend passes the signed manifest URL to the video player.
- **CDN (CloudFront / Cloudflare)** sits in front of S3.
- Manifest request: CDN forwards the signed URL to S3, validates signature → returns manifest.
- Segment requests: CDN caches and serves the public `.ts` files directly from edge, reducing S3 egress.
- Player requests manifest once, then fetches segments as needed — all segments are cacheable and publicly readable.

---

### Summary of the security model:

| Resource | Protected How | Rationale |
|----------|---------------|-----------|
| `.m3u8` manifest | Short-lived signed URL | The "key" to playback — must be guarded |
| `.ts` segments | Public (obfuscated paths) | Worthless without the manifest; enables CDN caching without signed cookie complexity |
| Thumbnails/poster | Public | No sensitive content risk |