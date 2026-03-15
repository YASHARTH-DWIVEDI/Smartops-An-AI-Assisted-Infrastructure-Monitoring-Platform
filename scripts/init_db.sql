-- SmartOps PostgreSQL Initialisation
-- Run automatically by docker-compose on first start

-- Create extensions
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create indexes after SQLAlchemy creates tables
-- (SQLAlchemy handles table creation; this adds extras)

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE smartops TO smartops;
