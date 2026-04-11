-- Grading Factors API — Initial Schema
-- Run this in the Supabase SQL editor (Database > SQL Editor > New query).
-- Safe to re-run: all statements use CREATE TABLE IF NOT EXISTS.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- grain_classes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS grain_classes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grain_id            text UNIQUE NOT NULL,
    grain_name          text NOT NULL,
    kind                text NOT NULL,           -- 'wheat' | 'oilseed' | 'pulse' | 'cereal'
    region              text,                    -- 'western' | 'eastern' | NULL
    use_class           text,                    -- 'malting' | 'food' | 'general_purpose' | NULL
    colour_modifier     boolean NOT NULL DEFAULT false,
    size_modifier       boolean NOT NULL DEFAULT false,
    source_url          text NOT NULL,
    effective_crop_year text NOT NULL,
    last_scraped        timestamptz NOT NULL,
    coverage_status     text NOT NULL,           -- 'complete' | 'partial'
    fallthrough_label   text,
    grade_floor_rules   jsonb NOT NULL DEFAULT '[]'::jsonb,
    grades              jsonb NOT NULL DEFAULT '[]'::jsonb,
    variety_tracks      jsonb,
    footnotes           jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS grain_classes_updated_at ON grain_classes;
CREATE TRIGGER grain_classes_updated_at
    BEFORE UPDATE ON grain_classes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- factor_groups
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS factor_groups (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grain_class_id  uuid NOT NULL REFERENCES grain_classes(id) ON DELETE CASCADE,
    group_id        text NOT NULL,
    group_label     text NOT NULL,
    sort_order      integer NOT NULL
);

-- ---------------------------------------------------------------------------
-- factors
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS factors (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    factor_group_id      uuid NOT NULL REFERENCES factor_groups(id) ON DELETE CASCADE,
    factor_id            text NOT NULL,
    factor_label         text NOT NULL,
    unit                 text,
    unit_alt             text,
    threshold_direction  text,                   -- 'maximum' | 'minimum' | NULL
    is_aggregate         boolean NOT NULL DEFAULT false,
    aggregates           jsonb,                  -- array of factor_id strings | NULL
    footnote_ref         text,
    thresholds           jsonb NOT NULL DEFAULT '{}'::jsonb,
    fallthrough          jsonb,                  -- string | array of condition objects | NULL
    sort_order           integer NOT NULL
);

-- ---------------------------------------------------------------------------
-- api_keys
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash     text UNIQUE NOT NULL,           -- SHA-256 hash of the actual key
    email        text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    is_active    boolean NOT NULL DEFAULT true
);

-- ---------------------------------------------------------------------------
-- changelog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS changelog (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_year          text NOT NULL,
    effective_date     date NOT NULL,
    grain_ids_affected jsonb NOT NULL DEFAULT '[]'::jsonb,
    summary            text NOT NULL,
    source_memo_url    text,
    created_at         timestamptz NOT NULL DEFAULT now()
);
