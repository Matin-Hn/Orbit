import os
import subprocess
import tempfile
import json

from celery import shared_task
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.video import Video
from app.services.storage import storage_service
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def transcode_video_task(self, video_id: int, original_key: str, bucket: str):
    """
    Celery task:
      1. Download original video from S3 to a temp file.
      2. Transcode to HLS (adaptive bitrate or single stream).
      3. Generate poster thumbnail.
      4. Upload HLS playlist & segments + poster to S3 (processed/ prefix).
      5. Update video record with HLS URL, poster URL, duration, status.
    """
    db: Session = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} not found")
            return

        # Update status to let user know transcoding started
        video.status = "processing"
        db.commit()

        # 1. Download original
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.mp4")
            logger.info(f"Downloading {original_key} from bucket {bucket} to {input_path}")
            storage_service.download_file(original_key, input_path)

            # 2. Get video duration (using ffprobe)
            duration = get_video_duration(input_path)
            video.duration_seconds = int(duration)
            db.commit()

            # 3. Transcode to HLS (single quality for simplicity, but can be extended)
            output_hls_dir = os.path.join(tmpdir, "hls")
            os.makedirs(output_hls_dir, exist_ok=True)
            master_playlist = transcode_to_hls_multi_quality(input_path, output_hls_dir)
            # master_playlist is local path to master.m3u8

            # 4. Generate poster thumbnail (at 5 seconds)
            if not video.thumbnail_url:
                poster_path = os.path.join(tmpdir, "poster.jpg")
                generate_thumbnail(input_path, poster_path, time_seconds=5)
            else:
                logger.info(f"Using user‑uploaded thumbnail: {video.thumbnail_key}")

            # 5. Upload HLS assets to S3 under processed/video_id/
            s3_prefix = f"processed/{video_id}/hls"
            for root, dirs, files in os.walk(output_hls_dir):
                logger.info(f"root: {root} --- dirs: {dirs} --- files: {files}")
                for file in files:
                    local_path = os.path.join(root, file)
                    remote_key = f"{s3_prefix}/{file}"
                    storage_service.upload_file(local_path, remote_key, content_type=get_mime_type(file))

            # Upload poster
            poster_key = f"processed/{video_id}/poster.jpg"
            storage_service.upload_file(poster_path, poster_key, content_type="image/jpeg")

            # 6. Build public URLs
            hls_manifest_url = storage_service.get_public_url(f"{s3_prefix}/master.m3u8")
            poster_url = storage_service.get_public_url(poster_key)

            # 7. Update DB
            video.hls_manifest_url = hls_manifest_url
            video.poster_url = poster_url
            video.status = "ready"
            video.thumbnail_url = poster_url   # optional
            db.commit()

            logger.info(f"Video {video_id} successfully processed.")

    except Exception as e:
        logger.exception(f"Transcoding failed for video {video_id}")
        if db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
                video.processing_error = str(e)
                db.commit()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


# ---- Helper functions (use ffmpeg/ffprobe from system) ----
def get_video_duration(file_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def get_video_stream_info(file_path: str) -> dict:
    """Return video width, height, and duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    video_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if not video_stream:
        raise ValueError("No video stream found")
    return {
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "duration": float(data["format"]["duration"])
    }

def transcode_to_hls_multi_quality(input_path: str, output_dir: str) -> str:
    """
    Generate adaptive HLS with multiple qualities.
    Returns path to master.m3u8.
    """
    # Define renditions (bitrate, resolution, name)
    renditions = [
        {"bitrate": "800k", "scale": "640:360", "name": "360p"},
        {"bitrate": "2500k", "scale": "1280:720", "name": "720p"},
        {"bitrate": "5000k", "scale": "1920:1080", "name": "1080p"},
    ]
    # Optional: get original resolution to avoid upscaling
    video_info = get_video_stream_info(input_path)
    orig_height = video_info["height"]

    variant_playlists = []
    for r in renditions:
        # Skip if output resolution exceeds original
        out_height = int(r["scale"].split(":")[1])
        if out_height > orig_height:
            continue
        variant_dir = os.path.join(output_dir, r["name"])
        os.makedirs(variant_dir, exist_ok=True)
        playlist_path = os.path.join(variant_dir, "playlist.m3u8")
        cmd = [
            "ffmpeg", "-i", input_path,
            "-c:v", "libx264", "-b:v", r["bitrate"],
            "-vf", f"scale={r['scale']}", "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", os.path.join(variant_dir, "segment_%03d.ts"),
            playlist_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        # Create variant entry for master playlist
        bandwidth = int(r["bitrate"].replace("k", "000"))
        variant_playlists.append({
            "path": f"{r['name']}/playlist.m3u8",
            "bandwidth": bandwidth,
            "resolution": r["scale"]
        })

    # Generate master playlist (variant.m3u8)
    master_path = os.path.join(output_dir, "master.m3u8")
    with open(master_path, "w") as f:
        f.write("#EXTM3U\n")
        for v in variant_playlists:
            f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={v["bandwidth"]},RESOLUTION={v["resolution"]}\n')
            f.write(f'{v["path"]}\n')
    return master_path

def generate_thumbnail(input_path: str, output_path: str, time_seconds: int = 5):
    subprocess.run(
        ["ffmpeg", "-i", input_path, "-ss", str(time_seconds),
         "-vframes", "1", "-q:v", "2", output_path],
        check=True, capture_output=True
    )

def get_mime_type(filename: str) -> str:
    if filename.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    elif filename.endswith(".ts"):
        return "video/MP2T"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    else:
        return "application/octet-stream"