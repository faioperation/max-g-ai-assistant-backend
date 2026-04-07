import io
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from .google_auth import GoogleAuthBase
from .meta_api import MetaAPI
import requests

logger = logging.getLogger(__name__)

class GoogleDriveService(GoogleAuthBase):
    """
    Service to handle Google Drive operations like folder creation and file upload.
    Inherits from GoogleAuthBase to share credentials with and CalendarService.
    """
    def __init__(self):
        super().__init__()
        if self.creds:
            self.service = build("drive", "v3", credentials=self.creds)
        else:
            self.service = None

    def get_or_create_folder(self, folder_name, parent_id=None):
        """
        Retrieves an existing folder ID or creates a new one.
        """
        if not self.service:
            return None

        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        try:
            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            items = results.get('files', [])

            if items:
                return items[0]['id']
            
            # Create if not exists
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            logger.info(f"Created folder: {folder_name} (ID: {folder.get('id')})")
            return folder.get('id')
        except Exception as e:
            logger.error(f"Error in get_or_create_folder: {str(e)}")
            return None

    def upload_file(self, content, filename, mime_type, folder_id):
        """
        Upload binary content as a file to a specific folder.
        """
        if not self.service:
            return None

        try:
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            logger.info(f"Uploaded file: {filename} (ID: {file.get('id')})")
            return file.get('id')
        except Exception as e:
            logger.error(f"Error uploading file to Drive: {str(e)}")
            return None

    def sync_whatsapp_media(self, contact_name, phone_number, media_id, mime_type, body_caption=None):
        """
        Main orchestrator to sync Meta media to Google Drive.
        1. Resolve folder structure
        2. Get media URL from Meta
        3. Download media
        4. Upload to Drive
        """
        if not self.service:
            logger.error("Drive service not initialized — check authentication")
            return None

        # 1. Resolve folder structure
        # Main folder: alex_communications
        main_folder_id = self.get_or_create_folder("alex_communications")
        if not main_folder_id:
            return None

        # Subfolder: {Name}_{Number}
        user_folder_name = f"{contact_name or 'user'}_{phone_number}"
        user_folder_id = self.get_or_create_folder(user_folder_name, parent_id=main_folder_id)
        if not user_folder_id:
            return None

        # Deep subfolder by type (img, pdf, video, etc.)
        type_folder_name = "others"
        mime_lower = mime_type.lower()
        if "image" in mime_lower:
            type_folder_name = "img"
        elif "pdf" in mime_lower:
            type_folder_name = "pdf"
        elif "video" in mime_lower:
            type_folder_name = "video"
        elif "audio" in mime_lower or "voice" in mime_lower:
            type_folder_name = "audio"
        elif "application" in mime_lower or "text" in mime_lower:
            type_folder_name = "docs"

        final_folder_id = self.get_or_create_folder(type_folder_name, parent_id=user_folder_id)
        if not final_folder_id:
            final_folder_id = user_folder_id # Fallback to user folder if deep nesting fails

        # 2. Get media URL from Meta
        meta_api = MetaAPI()
        media_info = meta_api.get_media_url(media_id)
        url = media_info.get("url")
        if not url:
            logger.error(f"Could not find media URL for ID: {media_id}")
            return None

        # 3. Download media
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {meta_api.access_token}"},
                timeout=30
            )
            if response.status_code != 200:
                logger.error(f"Failed to download media from Meta: {response.status_code}")
                return None
            
            content = response.content
            # Deduce extension from mime type
            import mimetypes
            ext = mimetypes.guess_extension(mime_type) or ""
            filename = f"WA_Media_{media_id}{ext}"
            if body_caption and len(body_caption) < 50:
                # Use caption as part of filename if reasonable
                safe_caption = "".join(x for x in body_caption if x.isalnum() or x in "._- ")
                filename = f"{safe_caption}_{media_id}{ext}"

            # 4. Upload to Drive
            return self.upload_file(content, filename, mime_type, final_folder_id)

        except Exception as e:
            logger.error(f"Sync error: {str(e)}")
            return None
