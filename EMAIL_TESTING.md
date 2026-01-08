# Email Ingestion Testing Guide

## Quick Start

1. **Configure Domain**
   ```bash
   export EMAIL_INGEST_DOMAIN=ingest.etlai.com
   ```

2. **Find Tenant Slug**
   ```sql
   SELECT slug, name FROM public.tenants WHERE status = 'active';
   ```

3. **Start Monitoring**
   ```bash
   python scripts/monitor_email_ingestion.py --watch
   ```

4. **Send Test Email**
   Send to: `{tenant-slug}@ingest.etlai.com`

5. **Verify Results** - The monitoring script shows:
   - ✅ Email received
   - ✅ Tenant information
   - ✅ Document IDs created
   - ✅ Attachment count

---

## Prerequisites

1. **Resend Domain Configuration**
   - Domain configured in Resend
   - Inbound email routing set up
   - Webhook: `https://www.etlai.xyz/api/v1/webhooks/email/inbound`

2. **Environment Variables**
   ```bash
   RESEND_WEBHOOK_SECRET=your_webhook_secret
   EMAIL_INGEST_DOMAIN=ingest.etlai.com
   ```

3. **Tenant Setup**
   - At least one tenant with valid `slug`
   - Tenant status must be `active`

## Email Address Format

```
{tenant-slug}@{EMAIL_INGEST_DOMAIN}
```

**Example**: If `EMAIL_INGEST_DOMAIN=ingest.etlai.com` and tenant slug is `acme-corp`:
- Send to: `acme-corp@ingest.etlai.com`

---

## Detailed Testing Steps

### 1. Configure Email Ingestion Domain

Add to `.env` file:
```bash
EMAIL_INGEST_DOMAIN=ingest.etlai.com
```

### 2. Verify Tenant Exists

```sql
SELECT id, slug, name, status FROM public.tenants WHERE status = 'active';
```

Note the `slug` value for the email address.

### 3. Start Monitoring

```bash
python scripts/monitor_email_ingestion.py --watch
```

Monitors continuously and displays real-time ingestions.

### 4. Send Test Email

**To:** `{tenant-slug}@{EMAIL_INGEST_DOMAIN}`

**Example:**
- From: `your-email@gmail.com`
- To: `acme-corp@ingest.etlai.com`
- Subject: `Test Email - Real Forward`
- Body: `This is a test email to verify ingestion.`
- (Optional) Attachments: PDF or documents

### 5. Verify Ingestion

Monitor script shows:
- Email received timestamp
- Tenant information
- From/To addresses
- Subject
- Attachment count
- Document IDs created

### 6. Check Database

```sql
-- Check email ingestion record
SELECT 
    id,
    tenant_id,
    from_address,
    to_address,
    subject,
    attachment_count,
    received_at
FROM public.email_ingestions
ORDER BY received_at DESC
LIMIT 10;

-- Check documents created
SELECT 
    id,
    tenant_id,
    original_filename,
    mime_type,
    file_size_bytes,
    source_type,
    status,
    parent_id
FROM public.documents
WHERE source_type = 'email'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Monitoring Commands

### One-time Check
```bash
# Check last 5 minutes
python scripts/monitor_email_ingestion.py

# Check last 30 minutes
python scripts/monitor_email_ingestion.py 30
```

### Continuous Monitoring
```bash
# Monitor every 10 seconds, look back 5 minutes
python scripts/monitor_email_ingestion.py --watch

# Monitor every 5 seconds, look back 10 minutes
python scripts/monitor_email_ingestion.py --watch 5 10
```

---

## Troubleshooting

### Email Not Received

1. **Check Resend Webhook Logs**
   - Go to Resend Dashboard → Webhooks
   - Check delivery logs
   - Look for HTTP status codes and errors

2. **Verify Webhook URL**
   - Ensure: `https://www.etlai.xyz/api/v1/webhooks/email/inbound`
   - Check endpoint is accessible (no auth required)

3. **Check Signature Verification**
   - Verify `RESEND_WEBHOOK_SECRET` matches Resend dashboard
   - Check application logs for "Invalid signature" errors

### Invalid Recipient Error

1. **Check Domain Configuration**
   - Verify `EMAIL_INGEST_DOMAIN` matches Resend inbound domain
   - Ensure recipient email uses correct domain

2. **Check Tenant Slug**
   - Verify: `SELECT slug FROM tenants WHERE slug = 'your-slug';`
   - Ensure slug matches email address prefix

### Rate Limit Exceeded

- Rate limit: 100 emails per sender per hour
- Wait for rate limit window to expire
- Check `email_ingestions` for recent emails from sender

### Tenant Not Found

- Verify tenant exists in database
- Check tenant `slug` matches email address prefix
- Ensure tenant `status` is `'active'`

---

## Testing with Attachments

1. Send email with PDF, Word, or image attachments
2. Monitor script shows attachment count
3. Check `documents` table for attachment records
4. Verify `parent_id` links attachments to body document

---

## Example Test Scenarios

### Scenario 1: Simple Text Email
```
From: test@example.com
To: acme-corp@ingest.etlai.com
Subject: Simple Test
Body: This is a simple test email.
```

### Scenario 2: Email with Attachment
```
From: test@example.com
To: acme-corp@ingest.etlai.com
Subject: Test with PDF
Body: Please find attached document.
Attachment: test-document.pdf
```

### Scenario 3: HTML Email
```
From: test@example.com
To: acme-corp@ingest.etlai.com
Subject: HTML Test
Body: <html><body><h1>Test</h1><p>HTML content</p></body></html>
```

---

## Production Checklist

Before going live:

- [ ] `EMAIL_INGEST_DOMAIN` is set correctly
- [ ] `RESEND_WEBHOOK_SECRET` is configured
- [ ] Webhook URL: `https://www.etlai.xyz/api/v1/webhooks/email/inbound`
- [ ] Resend inbound routing configured
- [ ] All tenants have valid slugs
- [ ] Monitoring set up
- [ ] Database migrations applied
- [ ] Rate limiting working
- [ ] Signature verification working

---

## Next Steps

After successful testing:

1. Configure Resend inbound routing for production
2. Set up alerting for failed ingestions
3. Monitor rate limits and adjust if needed
4. Document tenant email addresses for users
5. Set up regular monitoring and health checks

---

**Document Version**: 1.0  
**Last Updated**: January 7, 2026
