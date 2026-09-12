import json
import logging
import time
from uuid import UUID

import httpx

from modules.database import get_pool

logger = logging.getLogger(__name__)

# Marketing-site events.
WEB_EVENTS = ("page_view", "download_click")

# Desktop-app events.
APP_EVENTS = (
    "app_launch",
    "session_start",
    "session_end",
    "answer_requested",
    "screen_analysed",
    "quota_exceeded",
    "upgrade_clicked",
)

ALLOWED_EVENTS = WEB_EVENTS + APP_EVENTS

ALLOWED_SOURCES = ("web", "app")

GEO_LOOKUP_URL = "http://ip-api.com/json/{ip}?fields=status,country,regionName,city"
GEO_CACHE_TTL_SECONDS = 24 * 60 * 60

# ip -> (expires_at, {"country": ..., "region": ..., "city": ...})
_geo_cache: dict[str, tuple[float, dict]] = {}


def _coerce_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


async def insert_site_event(
    event: str,
    visitor_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    path: str | None = None,
    referrer: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_term: str | None = None,
    utm_content: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
    language: str | None = None,
    timezone: str | None = None,
    screen_w: int | None = None,
    screen_h: int | None = None,
    meta: dict | None = None,
    source: str = "web",
    app_version: str | None = None,
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.site_events (
                event, visitor_id, session_id, user_id, path, referrer,
                utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                user_agent, ip, language, timezone, screen_w, screen_h, meta,
                source, app_version
            )
            VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17, $18::jsonb,
                $19, $20
            )
            RETURNING id, event, created_at
            """,
            event,
            visitor_id,
            session_id,
            _coerce_uuid(user_id),
            path,
            referrer,
            utm_source,
            utm_medium,
            utm_campaign,
            utm_term,
            utm_content,
            user_agent,
            ip,
            language,
            timezone,
            screen_w,
            screen_h,
            json.dumps(meta or {}),
            source,
            app_version,
        )
    if not row:
        raise RuntimeError("site_events insert returned no row")
    return dict(row)


def _is_public_ip(ip: str | None) -> bool:
    if not ip:
        return False
    if ip in ("127.0.0.1", "::1", "localhost", "testclient"):
        return False
    return not (
        ip.startswith("10.")
        or ip.startswith("192.168.")
        or ip.startswith("172.16.")
        or ip.startswith("172.17.")
        or ip.startswith("172.18.")
        or ip.startswith("172.19.")
        or ip.startswith("172.2")
        or ip.startswith("172.30.")
        or ip.startswith("172.31.")
    )


async def lookup_geo(ip: str) -> dict | None:
    """
    Resolve country/region/city for an IP. Results are cached in-process so
    repeat visitors never trigger a second outbound call.
    """
    if not _is_public_ip(ip):
        return None

    cached = _geo_cache.get(ip)
    now = time.time()
    if cached and cached[0] > now:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(GEO_LOOKUP_URL.format(ip=ip))
            data = res.json()
    except Exception:
        logger.warning("geo lookup failed for ip=%s", ip, exc_info=True)
        return None

    if data.get("status") != "success":
        return None

    geo = {
        "country": data.get("country"),
        "region": data.get("regionName"),
        "city": data.get("city"),
    }
    _geo_cache[ip] = (now + GEO_CACHE_TTL_SECONDS, geo)
    return geo


async def update_event_geo(event_id, ip: str) -> None:
    """
    Background task: backfill geo columns for an already-inserted event.
    Never raises — analytics must not surface errors to the caller.
    """
    try:
        geo = await lookup_geo(ip)
        if not geo:
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.site_events
                SET country = $2, region = $3, city = $4
                WHERE id = $1
                """,
                event_id,
                geo.get("country"),
                geo.get("region"),
                geo.get("city"),
            )
    except Exception:
        logger.warning("geo backfill failed for event=%s", event_id, exc_info=True)
