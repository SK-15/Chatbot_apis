"""
Aggregates for the admin dashboard.

One entry point, `get_admin_stats`, runs every aggregate on a single
connection and returns a JSON-ready dict. Read-only throughout.
"""
from datetime import date, datetime, timedelta, timezone

from modules.database import get_pool

# Website tracking started mid-September 2026; anything before that is absent,
# not zero. The dashboard labels the affected figures with this date.
TRACKING_STARTED_ON = date(2026, 9, 12)

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365


def _rate(numerator: int, denominator: int) -> float | None:
    """Conversion percentage, or None when there is no base to divide by."""
    if not denominator:
        return None
    return round(numerator * 100.0 / denominator, 1)


def _zero_filled(rows: list[dict], start: date, end: date, keys: tuple[str, ...]) -> list[dict]:
    """
    Expand sparse per-day rows into one entry per day in the window, so a quiet
    day renders as a zero rather than vanishing from the chart.
    """
    by_day = {r["day"]: r for r in rows}
    out = []
    cursor = start
    while cursor <= end:
        row = by_day.get(cursor)
        entry = {"date": cursor.isoformat()}
        for k in keys:
            entry[k] = int(row[k]) if row and row.get(k) is not None else 0
        out.append(entry)
        cursor += timedelta(days=1)
    return out


async def get_admin_stats(days: int = DEFAULT_WINDOW_DAYS) -> dict:
    days = max(1, min(int(days or DEFAULT_WINDOW_DAYS), MAX_WINDOW_DAYS))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    start_day = since.date()
    end_day = now.date()

    pool = await get_pool()
    async with pool.acquire() as conn:
        # ── headline totals (all time) ──────────────────────────────────────
        users_total = await conn.fetchval('SELECT count(*) FROM neon_auth."user"')
        users_7d = await conn.fetchval(
            'SELECT count(*) FROM neon_auth."user" WHERE "createdAt" >= $1',
            now - timedelta(days=7),
        )
        users_window = await conn.fetchval(
            'SELECT count(*) FROM neon_auth."user" WHERE "createdAt" >= $1', since
        )
        sessions_total = await conn.fetchval("SELECT count(*) FROM public.interview_sessions")
        sessions_window = await conn.fetchval(
            "SELECT count(*) FROM public.interview_sessions WHERE started_at >= $1", since
        )
        # Only ended sessions have a duration worth averaging.
        avg_duration = await conn.fetchval(
            """
            SELECT avg(duration_seconds)::int
            FROM public.interview_sessions
            WHERE ended_at IS NOT NULL AND duration_seconds > 0
            """
        )
        sessions_ended = await conn.fetchval(
            "SELECT count(*) FROM public.interview_sessions WHERE ended_at IS NOT NULL"
        )

        # ── funnel over the window ──────────────────────────────────────────
        visitors = await conn.fetchval(
            """
            SELECT count(DISTINCT coalesce(visitor_id, id::text))
            FROM public.site_events
            WHERE event = 'page_view' AND source = 'web' AND created_at >= $1
            """,
            since,
        )
        page_views = await conn.fetchval(
            """
            SELECT count(*) FROM public.site_events
            WHERE event = 'page_view' AND source = 'web' AND created_at >= $1
            """,
            since,
        )
        downloads = await conn.fetchval(
            """
            SELECT count(*) FROM public.site_events
            WHERE event = 'download_click' AND created_at >= $1
            """,
            since,
        )
        downloaders = await conn.fetchval(
            """
            SELECT count(DISTINCT coalesce(visitor_id, id::text))
            FROM public.site_events
            WHERE event = 'download_click' AND created_at >= $1
            """,
            since,
        )

        # ── daily series ────────────────────────────────────────────────────
        signup_rows = await conn.fetch(
            """
            SELECT date_trunc('day', "createdAt")::date AS day, count(*) AS signups
            FROM neon_auth."user"
            WHERE "createdAt" >= $1
            GROUP BY 1
            """,
            since,
        )
        event_rows = await conn.fetch(
            """
            SELECT
                date_trunc('day', created_at)::date AS day,
                count(DISTINCT CASE WHEN event = 'page_view'
                      THEN coalesce(visitor_id, id::text) END) AS visitors,
                count(*) FILTER (WHERE event = 'download_click') AS downloads
            FROM public.site_events
            WHERE created_at >= $1 AND source = 'web'
            GROUP BY 1
            """,
            since,
        )
        session_rows = await conn.fetch(
            """
            SELECT date_trunc('day', started_at)::date AS day, count(*) AS sessions
            FROM public.interview_sessions
            WHERE started_at >= $1
            GROUP BY 1
            """,
            since,
        )

        # ── revenue (all time: too few purchases to window usefully) ────────
        revenue_total = await conn.fetchval("SELECT coalesce(sum(amount), 0) FROM public.purchases")
        paying_users = await conn.fetchval("SELECT count(DISTINCT user_id) FROM public.purchases")
        plan_rows = await conn.fetch(
            """
            SELECT plan_id, count(*) AS purchases, sum(amount) AS amount, sum(sessions) AS sessions
            FROM public.purchases
            GROUP BY plan_id
            ORDER BY sum(amount) DESC
            """
        )

        # ── traffic detail ──────────────────────────────────────────────────
        referrers = await conn.fetch(
            """
            SELECT coalesce(nullif(referrer, ''), 'direct') AS referrer, count(*) AS views
            FROM public.site_events
            WHERE event = 'page_view' AND created_at >= $1
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """,
            since,
        )
        pages = await conn.fetch(
            """
            SELECT coalesce(nullif(split_part(path, '?', 1), ''), '/') AS path, count(*) AS views
            FROM public.site_events
            WHERE event = 'page_view' AND created_at >= $1
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """,
            since,
        )
        campaigns = await conn.fetch(
            """
            SELECT utm_source, utm_medium, utm_campaign, count(*) AS views
            FROM public.site_events
            WHERE created_at >= $1 AND utm_source IS NOT NULL
            GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 10
            """,
            since,
        )
        countries = await conn.fetch(
            """
            SELECT country, count(DISTINCT coalesce(visitor_id, id::text)) AS visitors
            FROM public.site_events
            WHERE created_at >= $1 AND country IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """,
            since,
        )

        # ── desktop app events (empty until a build with analytics ships) ───
        app_rows = await conn.fetch(
            """
            SELECT event, count(*) AS n, count(DISTINCT visitor_id) AS installs
            FROM public.site_events
            WHERE source = 'app' AND created_at >= $1
            GROUP BY 1 ORDER BY 2 DESC
            """,
            since,
        )

    series = {
        r["day"]: {"signups": r["signups"]} for r in signup_rows
    }
    for r in event_rows:
        series.setdefault(r["day"], {}).update(
            {"visitors": r["visitors"], "downloads": r["downloads"]}
        )
    for r in session_rows:
        series.setdefault(r["day"], {}).update({"sessions": r["sessions"]})
    merged = [{"day": day, **vals} for day, vals in series.items()]

    return {
        "generated_at": now.isoformat(),
        "range_days": days,
        "tracking_started_on": TRACKING_STARTED_ON.isoformat(),
        "totals": {
            "users": users_total,
            "users_new_7d": users_7d,
            "users_new_window": users_window,
            "sessions": sessions_total,
            "sessions_window": sessions_window,
            "sessions_ended": sessions_ended,
            "avg_session_seconds": avg_duration or 0,
            "page_views": page_views,
            "downloads": downloads,
        },
        "funnel": {
            "visitors": visitors,
            "download_clicks": downloads,
            "unique_downloaders": downloaders,
            "signups": users_window,
            "sessions_started": sessions_window,
            "rates": {
                "visitor_to_download": _rate(downloaders, visitors),
                "download_to_signup": _rate(users_window, downloaders),
                "signup_to_session": _rate(sessions_window, users_window),
            },
        },
        "timeseries": _zero_filled(
            merged, start_day, end_day, ("signups", "visitors", "downloads", "sessions")
        ),
        "revenue": {
            "total_paise": int(revenue_total or 0),
            "paying_users": paying_users,
            "by_plan": [
                {
                    "plan_id": r["plan_id"],
                    "purchases": r["purchases"],
                    "amount_paise": int(r["amount"] or 0),
                    "sessions_sold": int(r["sessions"] or 0),
                }
                for r in plan_rows
            ],
        },
        "traffic": {
            "referrers": [dict(r) for r in referrers],
            "pages": [dict(r) for r in pages],
            "campaigns": [dict(r) for r in campaigns],
            "countries": [dict(r) for r in countries],
        },
        "app_events": [dict(r) for r in app_rows],
    }
