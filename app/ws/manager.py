import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.redis_client = None

    async def initialize(self):
        """Initialize Redis connection for pub/sub"""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_WS_PUBSUB,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("WebSocket manager: Redis connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise

    async def connect(self, video_id: int, websocket: WebSocket):
        await websocket.accept()
        if video_id not in self.active_connections:
            self.active_connections[video_id] = []
        self.active_connections[video_id].append(websocket)
        logger.info(f"WebSocket connected for video {video_id}")

    def disconnect(self, video_id: int, websocket: WebSocket):
        if video_id in self.active_connections:
            self.active_connections[video_id].remove(websocket)
            if not self.active_connections[video_id]:
                del self.active_connections[video_id]
            logger.info(f"WebSocket disconnected for video {video_id}")

    async def subscribe(self, video_id: int, websocket: WebSocket):
        """Listen on Redis channel and forward messages to the WebSocket."""
        if not self.redis_client:
            logger.error("Redis client not initialized")
            return
            
        pubsub = self.redis_client.pubsub()
        channel = f"video:{video_id}:status"
        
        try:
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                    logger.info(f"Sent message to WebSocket: {data}")
                    
                    # Once we send the "ready" event, we can unsubscribe
                    if data.get("type") == "video.ready":
                        logger.info(f"Video {video_id} is ready, unsubscribing")
                        break
                        
        except asyncio.CancelledError:
            logger.info(f"Subscription cancelled for video {video_id}")
        except Exception as e:
            logger.error(f"Error in subscription for video {video_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            logger.info(f"Unsubscribed from channel: {channel}")

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("WebSocket manager: Redis connection closed")

# Create global instance
manager = ConnectionManager()