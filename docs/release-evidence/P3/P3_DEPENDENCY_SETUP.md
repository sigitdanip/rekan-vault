# RekanVault — Phase 3 Dependency Setup Guide

**Created**: 2026-08-05  
**Purpose**: Step-by-step instructions for provisioning P3 external dependencies (Google Cloud, Notion) before P3 connector implementation begins.

---

## 1. Google Cloud — Drive & Docs API

### 1.1 Create Project & Enable APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project: `rekanvault-pilot` (or reuse existing)
3. Enable APIs:
   - **Google Drive API v3** — `https://www.googleapis.com/auth/drive.readonly`
   - **Google Docs API v1** — for `documents.get` structured content extraction
4. Go to **APIs & Services → Enabled APIs & services** and confirm both are listed

### 1.2 Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. **Create Credentials → OAuth client ID**
3. Application type: **Desktop app** (pilot) or **Web application**
4. Name: `RekanVault Pilot`
5. Add authorized redirect URI: `http://localhost:9002/api/v1/auth/callback/google`
6. Click **Create**
7. **Copy values into `.env`:**
   ```ini
   RV_GOOGLE_CLIENT_ID=<YOUR_CLIENT_ID>.apps.googleusercontent.com
   RV_GOOGLE_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
   ```

### 1.3 Get Pilot Refresh Token (One-Time Migration Path)

For the initial pilot, use `google-auth-oauthlib` flow to obtain a refresh token:

```bash
# This will be done via `rekanvault sources connect google` CLI command (TBD in P3)
# For now, you can use the Google OAuth Playground to get a refresh token:
#   1. Go to https://developers.google.com/oauthplayground
#   2. Configure with your client_id and client_secret (gear icon → "Use your own OAuth credentials")
#   3. Select scope: https://www.googleapis.com/auth/drive.readonly
#   4. Authorize → Exchange authorization code for tokens
#   5. Copy the refresh token
```

```ini
RV_GOOGLE_PILOT_REFRESH_TOKEN=<REFRESH_TOKEN>
```

### 1.4 Note the Target Google Drive Folder ID

Navigate to the Google Drive folder to ingest. The folder ID is in the URL:

```
https://drive.google.com/drive/folders/<FOLDER_ID>
```

```ini
RV_GOOGLE_FOLDER_ID=<FOLDER_ID>
```

### 1.5 Google OAuth Scope (ADRs Confirmed)

Per `RV-DEC-P3-0001`:
- Scope: `https://www.googleapis.com/auth/drive.readonly`
- Already set as default in `.env.example`
- Timeout: `RV_GOOGLE_API_TIMEOUT_SECONDS=30` (default)

---

## 2. Notion — Internal Integration & Webhook

### 2.1 Create Internal Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. **New integration**
3. Name: `RekanVault Pilot`
4. Associated workspace: your pilot workspace
5. Type: **Internal integration**
6. **Copy the Internal Integration Secret** (starts with `secret_`):
   ```ini
   RV_NOTION_TOKEN=secret_<YOUR_TOKEN>
   ```

### 2.2 Share Target Pages with Integration

For each Notion page/database you want RekanVault to access:

1. Open the page in Notion
2. Click **•••** (top-right) → **Connections**
3. Add **RekanVault Pilot** integration
4. For databases: also share the database itself (not just the parent page)

### 2.3 Note the Notion Root Page ID

The page ID is in the URL or Share link:
```
https://www.notion.so/sigit/<PAGE_TITLE>-<PAGE_ID>
```

```ini
RV_NOTION_PAGE_ID=<PAGE_ID>  (32-char hex, no hyphens)
```

### 2.4 Notion API Version

Per `RV-DEC-P3-0002` & SDLC plan:
- API version: `2026-03-11` (already set as default)
- Timeout: `RV_NOTION_API_TIMEOUT_SECONDS=30` (default)

### 2.5 Webhook Verification Token (for Public HTTPS)

Webhook setup requires a public HTTPS endpoint. For local dev, webhooks are deferred until staging/production.
When ready:

1. Generate a random verification token: `openssl rand -hex 32`
2. Configure in Notion integration settings → webhook URL
3. Set the verification token:
   ```ini
   RV_NOTION_WEBHOOK_VERIFICATION_TOKEN=<VERIFICATION_TOKEN>
   ```

**Note**: Notion webhooks are change *signals*, not canonical content. The connector refetches and reconciles per `RV-DEC-P3-0003`. For local development, rely on the 5-minute safety poll + daily reconciliation — webhook is not a blocking dependency for P3 implementation.

---

## 3. Polling Cadence (RV-DEC-P3-0003)

| Job | Interval | Notes |
|---|---|---|
| Drive `changes.list` incremental | 3 minutes | Starts from saved start-page token |
| Notion safety poll | 5 minutes | `last-edited-time` comparison |
| Full reconciliation | Daily (02:00 UTC) | Authoritative comparison with provider inventory |

Worker scheduler will read these from config. No additional env vars needed — cadence is config-driven.

---

## 4. File Size Cap (RV-DEC-P3-0004)

Already set in `.env.example`:
```ini
RV_MAX_SOURCE_FILE_BYTES=52428800  # 50 MiB
```

Files exceeding this raise `FILE_TOO_LARGE` diagnostic warning without crashing the worker.

---

## 5. `.env` Values to Fill

After provisioning, your `.env` should include these non-empty values:

```ini
# Google Drive OAuth
RV_GOOGLE_CLIENT_ID=<YOUR_CLIENT_ID>.apps.googleusercontent.com
RV_GOOGLE_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
RV_GOOGLE_PILOT_REFRESH_TOKEN=<REFRESH_TOKEN>
RV_GOOGLE_FOLDER_ID=<FOLDER_ID>

# Notion Integration
RV_NOTION_TOKEN=secret_<TOKEN>
RV_NOTION_PAGE_ID=<PAGE_ID>
RV_NOTION_WEBHOOK_VERIFICATION_TOKEN=  # deferred until staging
```

---

## 6. Post-Setup Verification

After filling credentials, P3 implementation can begin. First P3 to-do tests will exercise these credentials. The implementation sequence is:

1. Google Drive: OAuth callback → encrypted token storage → initial scan → changes feed → reconciliation
2. Notion: Integration token → root traversal → block parsing → safety poll → reconciliation
3. Shared: provider-neutral mutation contract → normalized blocks → extraction quality → source health API → Sources UI
