import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import redis as _redis
from rq import Queue

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()

# Initialized lazily in create_app
redis_client: _redis.Redis = None  # type: ignore
task_queue: Queue = None  # type: ignore


class DummyQueue:
    """No-op queue for development without Redis."""

    def enqueue(self, *args, **kwargs):
        logger.warning("Redis not available — skipping job enqueue: %s", args[:1])
        return None


def init_redis(app):
    global redis_client, task_queue
    redis_url = app.config.get("REDIS_URL", "")
    if not redis_url:
        logger.warning("REDIS_URL not set — queue disabled (dev mode)")
        task_queue = DummyQueue()
        return

    try:
        redis_client = _redis.from_url(redis_url, decode_responses=False)
        redis_client.ping()
        task_queue = Queue("ai-generation", connection=redis_client)
    except Exception as e:
        logger.warning("Redis connection failed (%s) — queue disabled", e)
        task_queue = DummyQueue()
