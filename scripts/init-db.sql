-- Email Summarizer Database Initialization Script

-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a schema for better organization
CREATE SCHEMA IF NOT EXISTS email_rag;

-- Set search path
SET search_path TO email_rag, public;

-- Create indexes for better performance
-- These will be created after the tables are created by SQLAlchemy

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA email_rag TO user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA email_rag TO user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA email_rag TO user;

-- Create a function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully';
END $$; 