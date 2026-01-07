/**
 * Auth0 Action: Add CAR Platform Custom Claims
 * 
 * This action injects custom claims into JWT tokens:
 * - https://car.platform/tenant_id: From user app_metadata.tenant_id
 * - https://car.platform/roles: Array of role strings from user app_metadata.roles
 * 
 * Trigger: Login / Post Login
 * 
 * Requirements:
 * - User must have app_metadata.tenant_id set
 * - User must have app_metadata.roles as an array (optional, defaults to [])
 */

exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://car.platform';
  
  // Extract tenant_id from user app_metadata
  const tenantId = event.user.app_metadata?.tenant_id;
  
  // Extract roles from user app_metadata (default to empty array)
  const roles = event.user.app_metadata?.roles || [];
  
  // Validate tenant_id is present
  if (!tenantId) {
    console.warn(`[CAR Claims] User ${event.user.user_id} missing tenant_id in app_metadata`);
    // Don't fail authentication, but log warning
    // In production, you may want to throw an error:
    // api.access.deny('User missing tenant_id');
  }
  
  // Validate roles is an array
  if (!Array.isArray(roles)) {
    console.warn(`[CAR Claims] User ${event.user.user_id} has invalid roles format, defaulting to []`);
    roles = [];
  }
  
  // Add tenant_id claim
  if (tenantId) {
    api.idToken.setCustomClaim(`${namespace}/tenant_id`, tenantId);
    api.accessToken.setCustomClaim(`${namespace}/tenant_id`, tenantId);
  }
  
  // Add roles claim (always add, even if empty array)
  api.idToken.setCustomClaim(`${namespace}/roles`, roles);
  api.accessToken.setCustomClaim(`${namespace}/roles`, roles);
  
  console.log(`[CAR Claims] Added claims for user ${event.user.user_id}: tenant_id=${tenantId}, roles=${JSON.stringify(roles)}`);
};
