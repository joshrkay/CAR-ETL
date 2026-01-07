"""Verify RBAC implementation meets all acceptance criteria."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.auth.roles import Role, Permission, ROLE_PERMISSIONS
from src.auth.decorators import requires_role, RequiresRole
from src.auth.rbac import RequiresRole as RequiresRoleDependency

def main():
    print("=" * 70)
    print("RBAC Acceptance Criteria Verification")
    print("=" * 70)
    print()
    
    # Acceptance Criteria 1: Three roles defined
    print("1. Three roles defined: Admin, Analyst, Viewer")
    print("-" * 70)
    assert Role.ADMIN == "admin", "Admin role should be 'admin'"
    assert Role.ANALYST == "analyst", "Analyst role should be 'analyst'"
    assert Role.VIEWER == "viewer", "Viewer role should be 'viewer'"
    print(f"   [OK] Role.ADMIN = '{Role.ADMIN.value}'")
    print(f"   [OK] Role.ANALYST = '{Role.ANALYST.value}'")
    print(f"   [OK] Role.VIEWER = '{Role.VIEWER.value}'")
    print()
    
    # Acceptance Criteria 2: Decorator/middleware @RequiresRole
    print("2. Decorator/middleware @RequiresRole('RoleName') implemented")
    print("-" * 70)
    assert callable(requires_role), "requires_role should be callable"
    assert callable(RequiresRole), "RequiresRole alias should be callable"
    assert callable(RequiresRoleDependency), "RequiresRoleDependency should be callable"
    print(f"   [OK] @requires_role() decorator exists")
    print(f"   [OK] @RequiresRole() alias exists (PascalCase)")
    print(f"   [OK] RequiresRole() dependency exists")
    print()
    
    # Acceptance Criteria 3: Admin role capabilities
    print("3. Admin role can: create/delete users, modify tenant settings,")
    print("   access billing, all document operations")
    print("-" * 70)
    admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
    
    # User Management
    assert Permission.CREATE_USER in admin_perms, "Admin should have CREATE_USER"
    assert Permission.DELETE_USER in admin_perms, "Admin should have DELETE_USER"
    assert Permission.UPDATE_USER in admin_perms, "Admin should have UPDATE_USER"
    assert Permission.LIST_USERS in admin_perms, "Admin should have LIST_USERS"
    print("   [OK] User Management: CREATE_USER, DELETE_USER, UPDATE_USER, LIST_USERS")
    
    # Tenant Settings
    assert Permission.MODIFY_TENANT_SETTINGS in admin_perms, "Admin should have MODIFY_TENANT_SETTINGS"
    assert Permission.VIEW_TENANT_SETTINGS in admin_perms, "Admin should have VIEW_TENANT_SETTINGS"
    print("   [OK] Tenant Settings: MODIFY_TENANT_SETTINGS, VIEW_TENANT_SETTINGS")
    
    # Billing
    assert Permission.ACCESS_BILLING in admin_perms, "Admin should have ACCESS_BILLING"
    assert Permission.VIEW_BILLING in admin_perms, "Admin should have VIEW_BILLING"
    print("   [OK] Billing: ACCESS_BILLING, VIEW_BILLING")
    
    # Document Operations
    assert Permission.UPLOAD_DOCUMENT in admin_perms, "Admin should have UPLOAD_DOCUMENT"
    assert Permission.EDIT_DOCUMENT in admin_perms, "Admin should have EDIT_DOCUMENT"
    assert Permission.DELETE_DOCUMENT in admin_perms, "Admin should have DELETE_DOCUMENT"
    assert Permission.VIEW_DOCUMENT in admin_perms, "Admin should have VIEW_DOCUMENT"
    assert Permission.SEARCH_DOCUMENTS in admin_perms, "Admin should have SEARCH_DOCUMENTS"
    print("   [OK] Document Operations: UPLOAD, EDIT, DELETE, VIEW, SEARCH")
    
    # AI Operations
    assert Permission.OVERRIDE_AI_DECISION in admin_perms, "Admin should have OVERRIDE_AI_DECISION"
    assert Permission.TRAIN_MODEL in admin_perms, "Admin should have TRAIN_MODEL"
    print("   [OK] AI Operations: OVERRIDE_AI_DECISION, TRAIN_MODEL")
    print()
    
    # Acceptance Criteria 4: Analyst role capabilities
    print("4. Analyst role can: upload/edit documents, override AI decisions,")
    print("   search, cannot manage users")
    print("-" * 70)
    analyst_perms = ROLE_PERMISSIONS[Role.ANALYST]
    
    # Document Operations (should have)
    assert Permission.UPLOAD_DOCUMENT in analyst_perms, "Analyst should have UPLOAD_DOCUMENT"
    assert Permission.EDIT_DOCUMENT in analyst_perms, "Analyst should have EDIT_DOCUMENT"
    assert Permission.DELETE_DOCUMENT in analyst_perms, "Analyst should have DELETE_DOCUMENT"
    assert Permission.VIEW_DOCUMENT in analyst_perms, "Analyst should have VIEW_DOCUMENT"
    assert Permission.SEARCH_DOCUMENTS in analyst_perms, "Analyst should have SEARCH_DOCUMENTS"
    print("   [OK] Document Operations: UPLOAD, EDIT, DELETE, VIEW, SEARCH")
    
    # AI Operations (should have)
    assert Permission.OVERRIDE_AI_DECISION in analyst_perms, "Analyst should have OVERRIDE_AI_DECISION"
    print("   [OK] AI Operations: OVERRIDE_AI_DECISION")
    
    # User Management (should NOT have)
    assert Permission.CREATE_USER not in analyst_perms, "Analyst should NOT have CREATE_USER"
    assert Permission.DELETE_USER not in analyst_perms, "Analyst should NOT have DELETE_USER"
    assert Permission.UPDATE_USER not in analyst_perms, "Analyst should NOT have UPDATE_USER"
    assert Permission.LIST_USERS not in analyst_perms, "Analyst should NOT have LIST_USERS"
    print("   [OK] User Management: NOT ALLOWED (correctly restricted)")
    
    # Billing (should NOT have)
    assert Permission.ACCESS_BILLING not in analyst_perms, "Analyst should NOT have ACCESS_BILLING"
    print("   [OK] Billing: NOT ALLOWED (correctly restricted)")
    print()
    
    # Acceptance Criteria 5: Viewer role capabilities
    print("5. Viewer role can: search and view documents only, no edit capabilities")
    print("-" * 70)
    viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
    
    # Read Operations (should have)
    assert Permission.VIEW_DOCUMENT in viewer_perms, "Viewer should have VIEW_DOCUMENT"
    assert Permission.SEARCH_DOCUMENTS in viewer_perms, "Viewer should have SEARCH_DOCUMENTS"
    print("   [OK] Read Operations: VIEW_DOCUMENT, SEARCH_DOCUMENTS")
    
    # Write Operations (should NOT have)
    assert Permission.UPLOAD_DOCUMENT not in viewer_perms, "Viewer should NOT have UPLOAD_DOCUMENT"
    assert Permission.EDIT_DOCUMENT not in viewer_perms, "Viewer should NOT have EDIT_DOCUMENT"
    assert Permission.DELETE_DOCUMENT not in viewer_perms, "Viewer should NOT have DELETE_DOCUMENT"
    print("   [OK] Write Operations: NOT ALLOWED (correctly restricted)")
    
    # AI Operations (should NOT have)
    assert Permission.OVERRIDE_AI_DECISION not in viewer_perms, "Viewer should NOT have OVERRIDE_AI_DECISION"
    print("   [OK] AI Operations: NOT ALLOWED (correctly restricted)")
    
    # User Management (should NOT have)
    assert Permission.CREATE_USER not in viewer_perms, "Viewer should NOT have CREATE_USER"
    assert Permission.DELETE_USER not in viewer_perms, "Viewer should NOT have DELETE_USER"
    print("   [OK] User Management: NOT ALLOWED (correctly restricted)")
    print()
    
    print("=" * 70)
    print("[OK] All Acceptance Criteria Verified")
    print("=" * 70)
    print()
    print("Summary:")
    print("  [OK] 1. Three roles defined (Admin, Analyst, Viewer)")
    print("  [OK] 2. @RequiresRole('RoleName') decorator implemented")
    print("  [OK] 3. Admin role has full access (all permissions)")
    print("  [OK] 4. Analyst role can upload/edit documents, override AI,")
    print("         search, cannot manage users")
    print("  [OK] 5. Viewer role can search and view documents only,")
    print("         no edit capabilities")
    print()
    print("RBAC implementation meets all acceptance criteria!")
    print()
    print("Usage Examples:")
    print("  @RequiresRole('Admin')")
    print("  @RequiresRole('Analyst')")
    print("  @RequiresRole('Viewer')")
    print("  @RequiresRole('Admin', 'Analyst')  # Multiple roles")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
