#!/usr/bin/env python3
"""
Verify Google Drive storage is properly configured.
Run this after setting up credentials.
"""
import asyncio
import os
import sys


async def verify():
    print("=" * 60)
    print("GOOGLE DRIVE STORAGE VERIFICATION")
    print("=" * 60)

    # Check environment
    folder_id = os.getenv("GDRIVE_ROOT_FOLDER_ID")
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/google_service_account.json")

    print(f"\n📋 Configuration:")
    print(f"   Folder ID: {folder_id or '❌ NOT SET'}")
    print(f"   Credentials: {creds_path}")
    print(f"   Creds exist: {'✅' if os.path.exists(creds_path) else '❌'}")

    if not folder_id:
        print("\n❌ GDRIVE_ROOT_FOLDER_ID not set!")
        print("   Run: set GDRIVE_ROOT_FOLDER_ID=your_folder_id")
        return False

    if not os.path.exists(creds_path):
        print(f"\n❌ Credentials file not found: {creds_path}")
        print("   Please place your Google service account JSON in credentials/")
        return False

    # Try to initialize storage
    print("\n🔄 Initializing storage...")
    try:
        from services import get_drive_storage
        storage = await get_drive_storage()

        if not storage._initialized:
            print("❌ Storage failed to initialize")
            return False

        print("✅ Storage initialized!")
        print(f"📁 Folders: {list(storage.folder_ids.keys())}")
    except Exception as e:
        print(f"❌ Storage init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test write
    print("\n🔄 Testing write...")
    try:
        from services import log_analytics
        doc_id = await log_analytics(
            event_type="verification_test",
            event_data={"status": "success", "test": True},
            session_id="verification-test"
        )
        print(f"✅ Test document written: {doc_id}")
    except Exception as e:
        print(f"❌ Write test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("✅ ALL CHECKS PASSED - Storage is ready!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(verify())
    sys.exit(0 if result else 1)
