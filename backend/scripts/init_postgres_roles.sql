-- Create read-only user for execution engine defense-in-depth (Rule R1.6)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'readonly_app_user') THEN

      CREATE ROLE readonly_app_user WITH LOGIN PASSWORD 'readonly_secret_pass';
   END IF;
END
$do$;

-- Default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_app_user;
