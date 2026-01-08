-- Fix auth hook to handle missing tables gracefully
CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  claims jsonb;
  user_tenant_id uuid;
  user_roles text[];
  tenant_slug text;
  user_id_val uuid;
BEGIN
  -- Extract user_id from the event
  user_id_val := (event->>'user_id')::uuid;
  
  -- Validate user_id exists
  IF user_id_val IS NULL THEN
    RETURN event;
  END IF;
  
  -- Try to query tenant_users and tenants tables
  -- Use exception handling to gracefully handle missing tables
  BEGIN
    SELECT tu.tenant_id, tu.roles, t.slug
    INTO user_tenant_id, user_roles, tenant_slug
    FROM public.tenant_users tu
    JOIN public.tenants t ON t.id = tu.tenant_id
    WHERE tu.user_id = user_id_val
    LIMIT 1;
  EXCEPTION
    WHEN undefined_table THEN
      -- Tables don't exist yet, return event unchanged
      RETURN event;
    WHEN OTHERS THEN
      -- Any other error, return event unchanged to prevent auth failures
      RETURN event;
  END;
  
  -- If user has no tenant assignment, return event unchanged
  IF user_tenant_id IS NULL THEN
    RETURN event;
  END IF;
  
  -- Get existing claims from the event
  claims := COALESCE(event->'claims', '{}'::jsonb);
  
  -- Ensure app_metadata exists in claims
  IF claims->'app_metadata' IS NULL THEN
    claims := jsonb_set(claims, '{app_metadata}', '{}'::jsonb);
  END IF;
  
  -- Inject tenant_id, roles, and tenant_slug into app_metadata
  claims := jsonb_set(claims, '{app_metadata,tenant_id}', to_jsonb(user_tenant_id));
  claims := jsonb_set(claims, '{app_metadata,roles}', to_jsonb(COALESCE(user_roles, ARRAY[]::text[])));
  
  -- Add tenant_slug if available
  IF tenant_slug IS NOT NULL THEN
    claims := jsonb_set(claims, '{app_metadata,tenant_slug}', to_jsonb(tenant_slug));
  END IF;
  
  -- Return the modified event with updated claims
  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;
