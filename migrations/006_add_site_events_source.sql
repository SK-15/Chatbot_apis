-- Distinguish marketing-site events from desktop-app events in the same table.
-- Existing rows are all from the website, which the default covers.

ALTER TABLE public.site_events
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'web',
    ADD COLUMN IF NOT EXISTS app_version text;

CREATE INDEX IF NOT EXISTS site_events_source_event_created_at_idx
    ON public.site_events (source, event, created_at DESC);
