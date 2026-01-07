#!/bin/bash
# Auth0 setup script for CAR Platform
# This script provides CLI commands for configuring Auth0 tenant

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables (should be set via environment or passed as arguments)
AUTH0_DOMAIN="${AUTH0_DOMAIN:-}"
AUTH0_CLIENT_ID="${AUTH0_CLIENT_ID:-}"
AUTH0_CLIENT_SECRET="${AUTH0_CLIENT_SECRET:-}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_auth0_cli() {
    if ! command -v auth0 &> /dev/null; then
        log_error "Auth0 CLI not found. Install it with: npm install -g @auth0/auth0-cli"
        exit 1
    fi
}

create_api_resource() {
    log_info "Creating API resource 'CAR API'..."
    
    auth0 apis create \
        --name "CAR API" \
        --identifier "https://api.car-platform.com" \
        --scopes "read:documents,write:documents,admin" \
        --signing-alg "RS256" \
        --description "CAR Platform API for document intelligence"
    
    log_info "API resource created successfully"
}

create_database_connection() {
    local connection_name="${1:-Username-Password-Authentication}"
    
    log_info "Creating database connection: ${connection_name}..."
    
    auth0 connections create database \
        --name "${connection_name}" \
        --enabled-clients "${AUTH0_CLIENT_ID}" \
        --password-policy "fair" \
        --password-complexity-options '{"min_length": 8, "require_lowercase": true, "require_uppercase": false, "require_numbers": true, "require_symbols": true}' \
        --description "CAR Platform database connection with password policy"
    
    log_info "Database connection created successfully"
}

create_management_api_client() {
    log_info "Creating Management API Machine-to-Machine application..."
    
    # Note: Management API client is typically created via Auth0 Dashboard
    # This is a reference for manual creation steps
    log_warn "Management API client must be created manually in Auth0 Dashboard:"
    log_warn "1. Go to Applications > Create Application"
    log_warn "2. Select 'Machine to Machine Applications'"
    log_warn "3. Authorize for 'Auth0 Management API'"
    log_warn "4. Grant permissions: read:users, create:users, update:users, delete:users"
    log_warn "5. Copy Client ID and Secret to environment variables"
}

configure_jwt_signing() {
    log_info "Verifying JWT signing algorithm is RS256..."
    
    # Get API details
    local api_id=$(auth0 apis list --json | jq -r '.[] | select(.identifier == "https://api.car-platform.com") | .id')
    
    if [ -z "$api_id" ]; then
        log_error "API resource not found. Create it first with create_api_resource"
        exit 1
    fi
    
    # Update signing algorithm
    auth0 apis update "$api_id" \
        --signing-alg "RS256"
    
    log_info "JWT signing algorithm configured to RS256"
}

setup_complete() {
    log_info "Auth0 setup complete!"
    log_info "Next steps:"
    log_info "1. Set environment variables:"
    log_info "   export AUTH0_DOMAIN=your-tenant.auth0.com"
    log_info "   export AUTH0_MANAGEMENT_CLIENT_ID=your-client-id"
    log_info "   export AUTH0_MANAGEMENT_CLIENT_SECRET=your-client-secret"
    log_info "   export AUTH0_DATABASE_CONNECTION_NAME=Username-Password-Authentication"
    log_info "2. Test connectivity: curl http://localhost:8000/health"
}

# Main execution
main() {
    log_info "Starting Auth0 setup for CAR Platform..."
    
    check_auth0_cli
    
    if [ -z "$AUTH0_DOMAIN" ]; then
        log_error "AUTH0_DOMAIN environment variable is required"
        exit 1
    fi
    
    create_api_resource
    create_database_connection
    create_management_api_client
    configure_jwt_signing
    setup_complete
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
