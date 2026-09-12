-- Site analytics events (page views + download button clicks) for the marketing site.

CREATE TABLE IF NOT EXISTS public.site_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event text NOT NULL,
    visitor_id text,
    session_id text,
    user_id uuid,
    path text,
    referrer text,
    utm_source text,
    utm_medium text,
    utm_campaign text,
    utm_term text,
    utm_content text,
    user_agent text,
    ip text,
    country text,
    region text,
    city text,
    language text,
    timezone text,
    screen_w integer,
    screen_h integer,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS site_events_event_created_at_idx
    ON public.site_events (event, created_at DESC);
CREATE INDEX IF NOT EXISTS site_events_visitor_id_idx
    ON public.site_events (visitor_id);
CREATE INDEX IF NOT EXISTS site_events_created_at_idx
    ON public.site_events (created_at DESC);
