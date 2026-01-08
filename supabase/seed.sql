-- Control plane: Seed data
-- System admin tenant for platform administration

-- Insert system admin tenant
-- This tenant is used for platform administration
INSERT INTO public.tenants (
  id,
  name,
  slug,
  environment,
  status,
  settings
) VALUES (
  '00000000-0000-0000-0000-000000000000'::uuid,
  'System Admin',
  'system-admin',
  'prod',
  'active',
  '{"is_system": true}'::jsonb
)
ON CONFLICT (slug) DO NOTHING;

-- Note: To add a user to this tenant, use:
-- INSERT INTO public.tenant_users (tenant_id, user_id, roles)
-- VALUES ('00000000-0000-0000-0000-000000000000'::uuid, '<user_id>', ARRAY['Admin']);
