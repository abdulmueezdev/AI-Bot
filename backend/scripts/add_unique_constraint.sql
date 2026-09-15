-- Add generated columns to allow a true UNIQUE constraint in PostgreSQL
-- (PostgreSQL does not support UNIQUE constraints on JSONB expressions directly, only UNIQUE INDEXES,
--  and PostgREST requires a named constraint or column names for 'on_conflict' in upserts).

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS source_file text GENERATED ALWAYS AS (metadata->>'source_file') STORED;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS chunk_index text GENERATED ALWAYS AS (metadata->>'chunk_index') STORED;

-- Add the unique constraint on the columns
ALTER TABLE documents 
ADD CONSTRAINT unique_clone_source_chunk UNIQUE (clone_id, source_file, chunk_index);
