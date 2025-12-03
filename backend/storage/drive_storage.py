# storage/drive_storage.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — GOOGLE DRIVE STORAGE
# ============================================================================
# Core Google Drive storage class with folder management and CRUD operations
# ============================================================================

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import asyncio

logger = logging.getLogger("BarriosA2I.Storage")


class DataType(Enum):
    """Data types with their folder mappings and retention policies."""
    CONVERSATIONS = ("01_Conversations", 365)
    SESSIONS = ("02_Sessions", 90)
    COMPETITIVE_INTEL = ("03_CompetitiveIntel", 365)
    PERSONAS = ("04_Personas", 365)
    SCRIPTS = ("05_Scripts", 180)
    ROI_CALCULATIONS = ("06_ROICalculations", 90)
    ANALYTICS = ("07_Analytics", 365)
    EMBEDDINGS = ("08_Embeddings", 365)
    LEADS = ("09_Leads", 730)
    ERRORS = ("10_Errors", 90)

    @property
    def folder_name(self) -> str:
        return self.value[0]

    @property
    def retention_days(self) -> int:
        return self.value[1]


class GoogleDriveStorage:
    """
    Google Drive storage manager for Website Assistant.

    Handles:
    - Automatic folder creation and management
    - JSON document storage and retrieval
    - Retention policy enforcement
    - Caching for frequently accessed data
    """

    def __init__(self):
        self.root_folder_id = os.getenv("GDRIVE_ROOT_FOLDER_ID")
        self.credentials_path = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "credentials/google_service_account.json"
        )
        self.folder_ids: Dict[str, str] = {}
        self._service = None
        self._initialized = False
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    async def initialize(self) -> bool:
        """Initialize Google Drive connection and create folder structure."""
        if self._initialized:
            return True

        if not self.root_folder_id:
            logger.warning("GDRIVE_ROOT_FOLDER_ID not set - storage disabled")
            return False

        if not os.path.exists(self.credentials_path):
            logger.warning(f"Credentials not found at {self.credentials_path}")
            return False

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            self._service = build('drive', 'v3', credentials=credentials)

            # Create folder structure
            await self._ensure_folders()

            self._initialized = True
            logger.info(f"Google Drive storage initialized with {len(self.folder_ids)} folders")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Google Drive storage: {e}")
            return False

    async def _ensure_folders(self):
        """Create all required folders if they don't exist."""
        for data_type in DataType:
            folder_name = data_type.folder_name
            folder_id = await self._get_or_create_folder(folder_name, self.root_folder_id)
            self.folder_ids[data_type.name] = folder_id
            logger.debug(f"Folder {folder_name}: {folder_id}")

    async def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        """Get existing folder or create new one."""
        # Search for existing folder
        query = f"name='{name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"

        def search():
            return self._service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, search)
        files = result.get('files', [])

        if files:
            return files[0]['id']

        # Create new folder
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }

        def create():
            return self._service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

        folder = await asyncio.get_event_loop().run_in_executor(None, create)
        logger.info(f"Created folder: {name}")
        return folder['id']

    async def store(
        self,
        data_type: DataType,
        data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        Store JSON data to Google Drive.

        Args:
            data_type: Type of data (determines folder and retention)
            data: Dictionary to store as JSON
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Google Drive file ID
        """
        if not self._initialized:
            await self.initialize()

        if not self._initialized:
            raise RuntimeError("Storage not initialized")

        folder_id = self.folder_ids.get(data_type.name)
        if not folder_id:
            raise ValueError(f"No folder for data type: {data_type}")

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            session_id = data.get("session_id", "unknown")[:8]
            filename = f"{timestamp}_{session_id}.json"

        # Add metadata
        data["_stored_at"] = datetime.utcnow().isoformat()
        data["_data_type"] = data_type.name
        data["_retention_days"] = data_type.retention_days

        # Upload to Drive
        from googleapiclient.http import MediaInMemoryUpload

        file_metadata = {
            'name': filename,
            'parents': [folder_id],
            'mimeType': 'application/json'
        }

        media = MediaInMemoryUpload(
            json.dumps(data, indent=2, default=str).encode('utf-8'),
            mimetype='application/json'
        )

        def upload():
            return self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, upload)
        file_id = result['id']

        logger.debug(f"Stored {data_type.name}: {filename} -> {file_id}")
        return file_id

    async def retrieve(
        self,
        data_type: DataType,
        limit: int = 100,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve JSON documents from Google Drive.

        Args:
            data_type: Type of data to retrieve
            limit: Maximum number of documents
            query_filter: Optional filter criteria

        Returns:
            List of documents
        """
        if not self._initialized:
            await self.initialize()

        if not self._initialized:
            return []

        folder_id = self.folder_ids.get(data_type.name)
        if not folder_id:
            return []

        # List files in folder
        query = f"'{folder_id}' in parents and trashed=false"

        def list_files():
            return self._service.files().list(
                q=query,
                pageSize=limit,
                orderBy='createdTime desc',
                fields='files(id, name, createdTime)'
            ).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, list_files)
        files = result.get('files', [])

        documents = []
        for file_info in files:
            try:
                doc = await self._download_json(file_info['id'])
                if doc:
                    doc['_file_id'] = file_info['id']
                    doc['_created_at'] = file_info.get('createdTime')

                    # Apply filter if provided
                    if query_filter:
                        if all(doc.get(k) == v for k, v in query_filter.items()):
                            documents.append(doc)
                    else:
                        documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to retrieve {file_info['id']}: {e}")

        return documents

    async def _download_json(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Download and parse a JSON file."""
        def download():
            return self._service.files().get_media(fileId=file_id).execute()

        content = await asyncio.get_event_loop().run_in_executor(None, download)
        return json.loads(content.decode('utf-8'))

    async def query_recent(
        self,
        data_type: DataType,
        hours: int = 24,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query recent documents within time window."""
        docs = await self.retrieve(data_type, limit=500)

        cutoff = datetime.utcnow().timestamp() - (hours * 3600)
        recent = []

        for doc in docs:
            created = doc.get('_created_at') or doc.get('_stored_at')
            if created:
                try:
                    if isinstance(created, str):
                        doc_time = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    else:
                        doc_time = created

                    if doc_time.timestamp() >= cutoff:
                        if session_id is None or doc.get('session_id') == session_id:
                            recent.append(doc)
                except:
                    pass

        return recent

    async def cleanup_expired(self, data_type: DataType) -> int:
        """Remove documents past their retention period."""
        if not self._initialized:
            return 0

        folder_id = self.folder_ids.get(data_type.name)
        if not folder_id:
            return 0

        retention_days = data_type.retention_days
        cutoff = datetime.utcnow().timestamp() - (retention_days * 86400)

        # List all files
        query = f"'{folder_id}' in parents and trashed=false"

        def list_files():
            return self._service.files().list(
                q=query,
                pageSize=1000,
                fields='files(id, createdTime)'
            ).execute()

        result = await asyncio.get_event_loop().run_in_executor(None, list_files)
        files = result.get('files', [])

        deleted = 0
        for file_info in files:
            created = file_info.get('createdTime')
            if created:
                try:
                    file_time = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    if file_time.timestamp() < cutoff:
                        def delete():
                            self._service.files().delete(fileId=file_info['id']).execute()
                        await asyncio.get_event_loop().run_in_executor(None, delete)
                        deleted += 1
                except:
                    pass

        if deleted:
            logger.info(f"Cleaned up {deleted} expired {data_type.name} documents")

        return deleted


# Singleton instance
_storage_instance: Optional[GoogleDriveStorage] = None


async def get_storage() -> GoogleDriveStorage:
    """Get or create the singleton storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = GoogleDriveStorage()
        await _storage_instance.initialize()
    return _storage_instance
