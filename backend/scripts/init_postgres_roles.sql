-- Create read-only user for execution engine defense-in-depth (Rule R1.6 / REQ-SAFE-04)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'business_readonly') THEN

      CREATE ROLE business_readonly WITH LOGIN PASSWORD 'readonly_secret_pass';
   END IF;
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'readonly_app_user') THEN

      CREATE ROLE readonly_app_user WITH LOGIN PASSWORD 'readonly_secret_pass';
   END IF;
END
$do$;

-- Read-only permissions on existing and future tables
GRANT USAGE ON SCHEMA public TO business_readonly, readonly_app_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO business_readonly, readonly_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO business_readonly, readonly_app_user;
