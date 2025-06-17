-- Script to update the embedding dimension for Gemini compatibility
-- This handles the dimension mismatch between OpenAI (1536) and Gemini (768)

-- First, backup the existing table if it has data
CREATE TABLE IF NOT EXISTS email_embeddings_backup AS SELECT * FROM email_embeddings;

-- Drop the existing embedding column
ALTER TABLE email_embeddings DROP COLUMN IF EXISTS embedding;

-- Add the new embedding column with 768 dimensions for Gemini
-- Note: You can change this to 1536 if using OpenAI or 3072 for gemini-embedding-001
ALTER TABLE email_embeddings ADD COLUMN embedding vector(768);

-- If you need to support multiple dimensions, you could create a more flexible approach:
-- Option 1: Use a larger dimension that can accommodate all models
-- ALTER TABLE email_embeddings ADD COLUMN embedding vector(3072);

-- Option 2: Store embeddings as JSONB and handle dimensions in application code
-- ALTER TABLE email_embeddings ADD COLUMN embedding JSONB;

COMMENT ON COLUMN email_embeddings.embedding IS 'Vector embedding with 768 dimensions for Gemini compatibility';

-- Grant necessary permissions
GRANT ALL ON TABLE email_embeddings TO email_user; 