"""utils/rate_limiter.py — Sliding window rate limiter"""
import time
from collections import defaultdict
from typing import Tuple

_user_windows = defaultdict(list)
_guild_windows = defaultdict(list)

DEFAULT_USER_LIMIT = 20
DEFAULT_GUILD_LIMIT = 200
WINDOW = 60


def check_rate_limit(guild_id: str, user_id: str, user_limit: int = None, guild_limit: int = None) -> Tuple[bool, str]:
    user_limit = user_limit or DEFAULT_USER_LIMIT
    guild_limit = guild_limit or DEFAULT_GUILD_LIMIT
    now = time.time()
    cutoff = now - WINDOW

    key = (guild_id, user_id)
    _user_windows[key] = [t for t in _user_windows[key] if t > cutoff]
    _guild_windows[guild_id] = [t for t in _guild_windows[guild_id] if t > cutoff]

    if len(_user_windows[key]) >= user_limit:
        remaining = int(_user_windows[key][0] + WINDOW - now)
        return False, f"⏱️ Rate limit reached. Try again in **{remaining}s**."

    if len(_guild_windows[guild_id]) >= guild_limit:
        remaining = int(_guild_windows[guild_id][0] + WINDOW - now)
        return False, f"⏱️ Server rate limit reached. Try again in **{remaining}s**."

    _user_windows[key].append(now)
    _guild_windows[guild_id].append(now)
    return True, ""