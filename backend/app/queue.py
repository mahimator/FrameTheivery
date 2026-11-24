from redis import Redis
from rq import Queue
from .config import REDIS_URL

redis_conn = Redis.from_url(REDIS_URL)
download_queue = Queue("downloads", connection=redis_conn, default_timeout=60 * 60 * 12)
