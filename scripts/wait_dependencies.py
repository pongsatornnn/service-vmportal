"""Wait for local dependencies without emitting credentials."""

import os
import time

from redis import Redis
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 2})
redis = Redis.from_url(
    os.environ["REDIS_URL"], socket_connect_timeout=2, socket_timeout=2
)
for _ in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        redis.ping()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Database or Redis not ready after 60 seconds")
engine.dispose()
redis.close()
