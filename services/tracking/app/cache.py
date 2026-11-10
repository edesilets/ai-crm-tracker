"""Latest known position per vehicle, kept in Redis for fast reads."""

import json
import logging
import os
from datetime import datetime

import redis

log = logging.getLogger(__name__)

client = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

# Only overwrite the cached position if the new ping is newer (pings can arrive out of order).
_SET_IF_NEWER = client.register_script(
    """
    local current = redis.call('GET', KEYS[1])
    if current then
        local cur = cjson.decode(current)
        if cur['_ts'] and cur['_ts'] >= tonumber(ARGV[2]) then
            return 0
        end
    end
    redis.call('SET', KEYS[1], ARGV[1])
    return 1
    """
)


def _key(vehicle_id: int) -> str:
    return f"vehicle:{vehicle_id}:location"


def set_latest(vehicle_id: int, ping: dict, recorded_at: datetime) -> None:
    ts = int(recorded_at.timestamp() * 1_000_000)  # microseconds since epoch
    try:
        _SET_IF_NEWER(keys=[_key(vehicle_id)], args=[json.dumps({**ping, "_ts": ts}), ts])
    except redis.RedisError:
        log.warning("Could not cache location for vehicle %s", vehicle_id, exc_info=True)


def get_latest(vehicle_id: int) -> dict | None:
    try:
        raw = client.get(_key(vehicle_id))
    except redis.RedisError:
        log.warning("Could not read cached location for vehicle %s", vehicle_id, exc_info=True)
        return None
    if not raw:
        return None
    data = json.loads(raw)
    data.pop("_ts", None)
    return data
