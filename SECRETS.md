# GitHub Secrets Configuration Guide

This document explains how to configure GitHub Secrets for the CI/CD workflows.

## Required Secrets

Configure these secrets in your GitHub repository settings:

### Repository Secrets (Available to all workflows)

1. **SUPABASE_URL**
   - Value: `https://ueqzwqejpjmsspfiypgb.supabase.co`
   - Used for: Connecting to Supabase in tests and deployments

2. **SUPABASE_ANON_KEY**
   - Value: Your Supabase anonymous key
   - Used for: Client-side Supabase operations

3. **SUPABASE_SERVICE_KEY**
   - Value: Your Supabase service role key
   - Used for: Server-side Supabase operations

4. **SUPABASE_JWT_SECRET**
   - Value: Your Supabase JWT secret
   - Used for: JWT token validation

5. **SUPABASE_PROJECT_REF**
   - Value: `ueqzwqejpjmsspfiypgb` (extracted from SUPABASE_URL)
   - Used for: Supabase CLI database push operations

6. **SUPABASE_ACCESS_TOKEN**
   - Value: Your Supabase access token for CLI authentication
   - Used for: Authenticating Supabase CLI in workflows
   - Get it from: https://supabase.com/dashboard/account/tokens

7. **OPENAI_API_KEY**
   - Value: Your OpenAI API key
   - Used for: AI service integrations

8. **RESEND_API_KEY**
   - Value: Your Resend API key
   - Used for: Email service operations

9. **RESEND_WEBHOOK_SECRET**
   - Value: Your Resend webhook signing secret (starts with `whsec_`)
   - Used for: Verifying Resend inbound webhook signatures
   - Get it from: Resend Dashboard → Webhooks → Your webhook → Signing Secret
   - Example format: `whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Webhook URL: `https://www.etlai.xyz/api/v1/webhooks/email/inbound`
   - **SECURITY WARNING**: Never commit real webhook secrets to version control. If a secret was previously exposed, rotate it immediately in the Resend dashboard.

10. **FLY_API_TOKEN**
   - Value: Your Fly.io API token
   - Used for: Deploying applications to Fly.io
   - Get it from: `flyctl auth token` or https://fly.io/user/personal_access_tokens

## Environment-Specific Secrets

Configure these in GitHub Environments (`staging` and `production`) for additional security:

### Staging Environment
- All repository secrets are available
- Can override with environment-specific values if needed

### Production Environment
- All repository secrets are available
- Can override with environment-specific values if needed

## How to Add Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its corresponding value
5. For environment-specific secrets, go to **Environments** → Select environment → **Add secret**

## Security Best Practices

- ✅ Never commit `.env` files to the repository
- ✅ Use `.env.example` as a template (without real values)
- ✅ Rotate secrets regularly
- ✅ Use different secrets for staging and production when possible
- ✅ Limit access to repository secrets to trusted team members
- ✅ Review secret usage in workflow logs (values are masked)

## Local Development

For local development, create a `.env` file in the project root (this file is gitignored):

```bash
# Copy the example file
cp .env.example .env

# Edit with your actual values
# (Never commit this file!)
```

## Project Reference Extraction

From your SUPABASE_URL: `https://ueqzwqejpjmsspfiypgb.supabase.co`

The project reference is: **ueqzwqejpjmsspfiypgb**

This should be set as `SUPABASE_PROJECT_REF` secret.
