your_project_name/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── README.md
├── alembic.ini
├── scripts/
│   ├── prestart.sh
│   └── entrypoint.sh
└── app/
    ├── __init__.py
    ├── main.py
    ├── core/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── security.py
    │   ├── database.py
    │   ├── redis_client.py
    │   ├── s3_client.py
    │   └── websocket_manager.py
    ├── models/
    │   ├── __init__.py
    │   ├── user.py
    │   ├── channel.py
    │   ├── post.py
    │   ├── live_stream.py
    │   ├── comment.py
    │   └── like.py
    ├── schemas/
    │   ├── __init__.py
    │   ├── user.py
    │   ├── channel.py
    │   ├── post.py
    │   ├── live_stream.py
    │   └── comment.py
    ├── api/
    │   ├── __init__.py
    │   ├── deps.py
    │   └── v1/
    │       ├── __init__.py
    │       ├── endpoints/
    │       │   ├── __init__.py
    │       │   ├── auth.py
    │       │   ├── users.py
    │       │   ├── channels.py
    │       │   ├── posts.py
    │       │   ├── live.py
    │       │   ├── comments.py
    │       │   └── search.py
    │       └── websockets/
    │           ├── __init__.py
    │           ├── chat.py
    │           └── stream_status.py
    ├── crud/
    │   ├── users_crud.py
    │   └── videos.py
    ├── services/
    │   ├── __init__.py
    │   ├── channel_service.py
    │   ├── post_service.py
    │   ├── stream_service.py
    │   ├── video_processor.py
    │   ├── notification_service.py
    │   └── analytics_service.py
    ├── tasks/
    │   ├── __init__.py
    │   ├── celery_app.py
    │   ├── transcoding_tasks.py
    │   └── cleanup_tasks.py
    ├── middleware/
    │   ├── __init__.py
    │   ├── rate_limit.py
    │   ├── logging.py
    │   └── cors.py
    └── utils/
        ├── __init__.py
        ├── pagination.py
        ├── validators.py
        └── helpers.py