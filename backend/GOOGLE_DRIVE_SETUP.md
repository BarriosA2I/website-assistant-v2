# Google Drive Storage Setup Guide

## Overview

Website Assistant v2.0 supports persistent storage to Google Drive for:
- **Conversations** - All chat turns
- **Cards** - CompetitorCard, PersonaCard, ScriptPreviewCard, ROICalculatorCard
- **Analytics** - Event tracking
- **Leads** - Captured lead information

## Prerequisites

1. Google Cloud Project
2. Service Account with Drive API access
3. Google Drive folder shared with service account

---

## Step 1: Create Google Cloud Project

1. Go to https://console.cloud.google.com
2. Click "Select a project" → "New Project"
3. Name: `barrios-a2i-storage` (or your preferred name)
4. Click "Create"

---

## Step 2: Enable Google Drive API

1. In your project, go to **APIs & Services → Library**
2. Search for "Google Drive API"
3. Click **Enable**

---

## Step 3: Create Service Account

1. Go to **IAM & Admin → Service Accounts**
2. Click **+ Create Service Account**
3. Name: `website-assistant-storage`
4. Click **Create and Continue**
5. Skip roles (not needed for Drive)
6. Click **Done**

---

## Step 4: Generate JSON Key

1. Click on your new service account
2. Go to **Keys** tab
3. Click **Add Key → Create new key**
4. Select **JSON**
5. Click **Create**
6. Save the downloaded file as:
   ```
   backend/credentials/google_service_account.json
   ```

---

## Step 5: Create Google Drive Folder

1. Go to https://drive.google.com
2. Create a new folder: `BarriosA2I_WebsiteAssistant`
3. Right-click → Share
4. Add the service account email (from the JSON file, looks like: `something@project-id.iam.gserviceaccount.com`)
5. Give it **Editor** access
6. Copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_HERE
   ```

---

## Step 6: Configure Environment

Create or update `backend/.env`:

```bash
# Google Drive Configuration
GDRIVE_ROOT_FOLDER_ID=your_folder_id_here
GOOGLE_APPLICATION_CREDENTIALS=credentials/google_service_account.json

# Existing configuration
ANTHROPIC_API_KEY=your_key_here
```

---

## Step 7: Install Dependencies

```bash
cd backend
./venv/Scripts/pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```

---

## Step 8: Verify Setup

```bash
cd backend
set PYTHONPATH=.
set GDRIVE_ROOT_FOLDER_ID=your_folder_id
./venv/Scripts/python verify_storage.py
```

Expected output:
```
============================================================
GOOGLE DRIVE STORAGE VERIFICATION
============================================================

📋 Configuration:
   Folder ID: 1abc...xyz
   Credentials: credentials/google_service_account.json
   Creds exist: ✅

🔄 Initializing storage...
✅ Storage initialized!
📁 Folders: ['CONVERSATIONS', 'SESSIONS', 'COMPETITIVE_INTEL', ...]

🔄 Testing write...
✅ Test document written: 1def...uvw

============================================================
✅ ALL CHECKS PASSED - Storage is ready!
============================================================
```

---

## Folder Structure

After initialization, Google Drive will contain:

```
BarriosA2I_WebsiteAssistant/
├── 01_Conversations/     # Chat logs (365 day retention)
├── 02_Sessions/          # Session summaries (90 days)
├── 03_CompetitiveIntel/  # CompetitorCard data (365 days)
├── 04_Personas/          # PersonaCard data (365 days)
├── 05_Scripts/           # ScriptPreviewCard data (180 days)
├── 06_ROICalculations/   # ROICalculatorCard data (90 days)
├── 07_Analytics/         # Event logs (365 days)
├── 08_Embeddings/        # Vector embeddings (365 days)
├── 09_Leads/             # Lead data (730 days)
└── 10_Errors/            # Error logs (90 days)
```

---

## API Endpoints

### Check Storage Status
```bash
curl http://localhost:8080/api/v2/storage/status
```

### Capture Lead
```bash
curl -X POST http://localhost:8080/api/v2/capture-lead \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test User"}'
```

---

## Troubleshooting

### "Module not found" error
```bash
./venv/Scripts/pip install google-api-python-client
```

### "Credentials not found" error
Ensure `credentials/google_service_account.json` exists and is readable.

### "Folder not found" error
1. Verify GDRIVE_ROOT_FOLDER_ID is correct
2. Ensure service account has Editor access to the folder
3. Check folder isn't in trash

### Storage works but slow
Google Drive API has rate limits. For high-volume production, consider:
- Redis caching layer
- Batch writes
- Async background persistence

---

## Production Notes

- **Rate Limits**: Google Drive API allows 1000 queries/100 seconds
- **Storage**: 30TB available (you're set for 1500+ years at 20GB/year)
- **Retention**: Automatic cleanup runs based on DataType retention policies
- **Fallback**: If storage fails, the app continues without persistence

---

## Security

- Never commit `credentials/google_service_account.json` to git
- Add to `.gitignore`:
  ```
  credentials/
  *.json
  ```
- Rotate service account keys periodically
- Use folder-level sharing, not file-level
