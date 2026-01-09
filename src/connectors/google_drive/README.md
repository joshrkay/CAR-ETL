# Google Drive Connector

Ingestion Plane connector for syncing files from Google Drive.

## Architecture

This connector is part of the **Ingestion Plane** and follows strict architectural boundaries:

- **Only captures and buffers data** - does not parse/extract business meaning
- **Emits normalized ingestion references** - does not download file bytes directly
- **Append-only ingestion** - never overwrites or deletes raw artifacts silently
- **Tenant isolation** - all operations scoped by tenantId
- **Idempotent sync** - retries do not create duplicates

## Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Web application"
   - Authorized redirect URIs: Add your callback URL (e.g., `https://yourdomain.com/api/v1/connectors/google_drive/callback`)
   - Save and note the **Client ID** and **Client Secret**

## Required Environment Variables

```bash
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback
```

**Security Note**: Never commit these credentials to version control. Use environment variables or a secrets management system.

## Folder Selection

The connector supports selecting one or more folders to sync:

- **No folders selected**: Syncs root of all accessible drives
- **Folders selected**: Only syncs files within selected folders (and subfolders)
- **Multiple folders**: Can sync from multiple folders simultaneously

Folder selection is persisted via `ConnectorConfigStore` interface and can be updated via API.

## Shared Drive Support

The connector supports Google Workspace shared drives (formerly Team Drives):

- **No shared drives specified**: Syncs from all accessible drives (My Drive + shared drives)
- **Shared drives specified**: Only syncs from specified shared drive IDs
- **Mixed mode**: Can sync from My Drive and specific shared drives

Shared drive IDs are persisted in connector configuration.

## Sync Mechanism

### Incremental Sync via Changes API

The connector uses Google Drive Changes API for efficient incremental sync:

1. **Initial sync**: Gets `startPageToken` to begin tracking changes
2. **Incremental sync**: Uses stored `pageToken` to fetch only changes since last sync
3. **Checkpointing**: Saves `pageToken` after each successful sync batch
4. **Idempotency**: Tracks processed file IDs per sync run to prevent duplicates

### Failure Handling

- **Token revoked/expired**: Marks connector as `needs_reauth`, stops sync
- **startPageToken invalidated**: Falls back to full resync with new token (no data loss)
- **File deleted/trashed**: Emits deletion reference event (append-only, no hard delete)
- **Permission denied**: Records error, continues best-effort, surfaces summary
- **Rate limits**: Exponential backoff with retry (bounded, max 5 minutes)

## What Sync Emits

The connector emits **normalized ingestion references**, not raw file data:

### File Reference Event

```json
{
  "id": "ingestion-event-id",
  "tenant_id": "tenant-uuid",
  "source_type": "google_drive",
  "source_path": "google_drive:my_drive:file-id",
  "file_id": "google-drive-file-id",
  "file_name": "redacted-filename.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 1024,
  "modified_time": "2024-01-01T00:00:00Z",
  "drive_id": null,
  "folder_ids": ["parent-folder-id"],
  "status": "pending"
}
```

### Deletion Reference Event

Marks existing ingestion records as deleted (append-only):

```json
{
  "status": "deleted",
  "error_message": "File deleted from Google Drive"
}
```

**Note**: The connector does NOT download file bytes. Downstream ingestion pipeline will:
1. Receive ingestion reference events
2. Fetch file bytes from Google Drive API using `file_id`
3. Store raw artifacts to S3
4. Produce `IngestionEvent` for Understanding Plane

## Security & Privacy

- **Explicit redaction**: File names are redacted via Presidio before persistence
- **No PII in logs**: Only logs IDs and metadata, never raw payloads
- **Token encryption**: OAuth tokens encrypted at rest via `TokenStore` interface
- **Tenant isolation**: All operations strictly scoped by tenantId

## Interfaces

The connector uses clean interfaces for storage and emission:

- `TokenStore`: OAuth token storage/retrieval
- `ConnectorConfigStore`: Configuration persistence
- `SyncStateStore`: Sync checkpoint management
- `IngestionEmitter`: Normalized event emission

These interfaces enable testability and maintain architectural boundaries.

## Testing

See `tests/test_google_drive_connector.py` for:
- Unit tests for OAuth, client, sync logic
- Property-based tests for idempotency
- Failure mode tests (revoked tokens, rate limits, invalid tokens)
