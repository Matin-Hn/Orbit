import os
import subprocess
import tempfile
import json
import math
from PIL import Image  
import logging

from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.video import Video
from app.services.storage import storage_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# app/tasks/video_tasks.py – update the main task

@shared_task(bind=True, max_retries=2)
def transcode_video_task(self, video_id: int, original_key: str, bucket: str):
    """
    Celery task:
      1. Download original video from S3 to a temp file.
      2. Transcode to HLS (adaptive bitrate or single stream).
      3. Transcode to multi-quality HLS
      4. Generate sprite images
      5. Generate poster thumbnail.
      6. Upload HLS playlist & segments + poster to S3 (processed/ prefix).
      7. Update video record with HLS URL, poster URL, duration, status.
    """
    db: Session = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} not found")
            return

        video.status = "processing"
        db.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.mp4")
            logger.info(f"Downloading {original_key} from bucket {bucket}")
            storage_service.download_file(original_key, input_path)

            # Get video duration
            video_info = get_video_stream_info(input_path)
            duration = video_info["duration"]
            video.duration_seconds = int(duration)
            db.commit()

            # Transcode to multi-quality HLS
            output_hls_dir = os.path.join(tmpdir, "hls")
            os.makedirs(output_hls_dir, exist_ok=True)
            master_playlist = transcode_to_hls_multi_quality(input_path, output_hls_dir)

            # Generate sprites for timeline preview
            sprite_output_dir = os.path.join(tmpdir, "sprites")
            os.makedirs(sprite_output_dir, exist_ok=True)
            sprite_data = generate_video_sprites(input_path, sprite_output_dir, duration)

            # Upload HLS assets
            hls_prefix = f"processed/{video_id}/hls"
            for root, dirs, files in os.walk(output_hls_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    remote_key = f"{hls_prefix}/{os.path.relpath(local_path, output_hls_dir)}"
                    storage_service.upload_file(local_path, remote_key, content_type=get_mime_type(file))

            # Upload sprite assets
            sprite_prefix = f"processed/{video_id}/sprites"
            sprite_local_path = os.path.join(sprite_output_dir, "sprites.jpg")
            vtt_local_path = os.path.join(sprite_output_dir, "sprites.vtt")
            
            sprite_remote_key = f"{sprite_prefix}/sprites.jpg"
            vtt_remote_key = f"{sprite_prefix}/sprites.vtt"
            
            storage_service.upload_file(sprite_local_path, sprite_remote_key, content_type="image/jpeg")
            storage_service.upload_file(vtt_local_path, vtt_remote_key, content_type="text/vtt")

            # Generate or use user-uploaded thumbnail
            if video.thumbnail_key:
                # User provided custom thumbnail
                video.thumbnail_url = storage_service.get_public_url(video.thumbnail_key)
                logger.info(f"Using user-uploaded thumbnail: {video.thumbnail_key}")
            else:
                # Generate poster from first frame
                poster_path = os.path.join(tmpdir, "poster.jpg")
                generate_thumbnail(input_path, poster_path, time_seconds=0)
                poster_key = f"processed/{video_id}/poster.jpg"
                storage_service.upload_file(poster_path, poster_key, content_type="image/jpeg")
                video.thumbnail_url = storage_service.get_public_url(poster_key)
                video.thumbnail_key = poster_key

            # Build public URLs
            hls_manifest_url = storage_service.get_public_url(f"{hls_prefix}/master.m3u8")
            sprite_url = storage_service.get_public_url(sprite_remote_key)
            sprite_vtt_url = storage_service.get_public_url(vtt_remote_key)

            # Update database with all metadata
            video.hls_manifest_url = hls_manifest_url
            video.sprite_url = sprite_url
            video.sprite_vtt_url = sprite_vtt_url
            video.sprite_tile_width = sprite_data["tile_width"]
            video.sprite_tile_height = sprite_data["tile_height"]
            video.sprite_columns = sprite_data["columns"]
            video.sprite_rows = sprite_data["rows"]
            video.status = "ready"
            db.commit()

            logger.info(f"Video {video_id} processed successfully with sprites")

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

def generate_video_sprites(input_path: str, output_dir: str, video_duration: float) -> dict:
    """
    Generate sprite sheet and VTT file for timeline preview.
    
    Args:
        input_path: Path to input video file
        output_dir: Directory to save generated files
        video_duration: Duration in seconds
    
    Returns:
        Dictionary with sprite metadata:
        {
            "sprite_url": "processed/{video_id}/sprites.jpg",
            "sprite_vtt_url": "processed/{video_id}/sprites.vtt",
            "tile_width": 160,
            "tile_height": 90,
            "columns": 10,
            "rows": 5
        }
    """
    # Configuration
    sprite_interval = settings.SPRITE_INTERVAL     # seconds between thumbnails
    tile_width = settings.SPRITE_TILE_WIDTH        # width of each thumbnail
    tile_height = settings.SPRITE_TILE_HEIGHT      # height of each thumbnail (16:9)
    columns = settings.SPRITE_COLUMNS              # number of tiles per row
    max_tiles = settings.SPRITE_MAX_TILES          # maximum sprites to generate (avoid huge files)
    
    # Calculate number of thumbnails needed
    num_thumbnails = min(math.ceil(video_duration / sprite_interval), max_tiles)
    rows = math.ceil(num_thumbnails / columns)
    
    # Create a temporary directory for individual thumbnails
    thumbnails_dir = os.path.join(output_dir, "thumbnails_temp")
    os.makedirs(thumbnails_dir, exist_ok=True)
    
    # Extract thumbnails at intervals using FFmpeg
    thumbnail_pattern = os.path.join(thumbnails_dir, "thumb_%04d.jpg")
    ffmpeg_cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", f"fps=1/{sprite_interval},scale={tile_width}:{tile_height}",
        "-frames:v", str(num_thumbnails),
        "-q:v", "3",  # Quality (2-5 is good for JPEG)
        thumbnail_pattern
    ]
    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    
    # Get list of generated thumbnails
    thumb_files = sorted([f for f in os.listdir(thumbnails_dir) if f.endswith('.jpg')])
    thumb_paths = [os.path.join(thumbnails_dir, f) for f in thumb_files]
    
    # Create sprite sheet using Pillow
    sprite_width = columns * tile_width
    sprite_height = rows * tile_height
    sprite_image = Image.new('RGB', (sprite_width, sprite_height), (0, 0, 0))
    
    for idx, thumb_path in enumerate(thumb_paths):
        if idx >= num_thumbnails:
            break
        col = idx % columns
        row = idx // columns
        x = col * tile_width
        y = row * tile_height
        
        thumb = Image.open(thumb_path)
        sprite_image.paste(thumb, (x, y))
        thumb.close()
    
    # Save sprite sheet
    sprite_path = os.path.join(output_dir, "sprites.jpg")
    sprite_image.save(sprite_path, quality=85, optimize=True)
    sprite_image.close()
    
    # Generate VTT file
    vtt_path = os.path.join(output_dir, "sprites.vtt")
    with open(vtt_path, "w") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        
        for idx in range(num_thumbnails):
            start_time = idx * sprite_interval
            end_time = min((idx + 1) * sprite_interval, video_duration)
            
            # Format time as HH:MM:SS.mmm
            start_str = format_time(start_time)
            end_str = format_time(end_time)
            
            col = idx % columns
            row = idx // columns
            x = col * tile_width
            y = row * tile_height
            
            vtt_file.write(f"{start_str} --> {end_str}\n")
            vtt_file.write(f"sprites.jpg#xywh={x},{y},{tile_width},{tile_height}\n\n")
    
    # Clean up temporary thumbnails
    shutil.rmtree(thumbnails_dir)
    
    return {
        "sprite_filename": "sprites.jpg",
        "vtt_filename": "sprites.vtt",
        "tile_width": tile_width,
        "tile_height": tile_height,
        "columns": columns,
        "rows": rows
    }

def format_time(seconds: float) -> str:
    """Convert seconds to VTT timestamp format HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"