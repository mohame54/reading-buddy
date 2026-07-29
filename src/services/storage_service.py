import os
from datetime import timedelta
from typing import Optional

from src.bq.utils import get_client_bucket, load_gcp_bucket_client


class StorageService:
    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_b64: Optional[str] = None,
    ):
        creds = credentials_b64 or os.environ["GOOGLE_CREDENTIALS"]
        proj = project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("PROJECT_ID", "").split(".")[0]
        self.bucket_name = bucket_name
        self.client = load_gcp_bucket_client(creds, proj_id=proj, from_b64=True)
        self.bucket = get_client_bucket(self.client, bucket_name)

    def _gcs_uri(self, object_name: str) -> str:
        return f"gs://{self.bucket_name}/{object_name}"

    def upload_doc(self, doc_id: str, ext: str, raw_bytes: bytes) -> str:
        object_name = f"docs/{doc_id}.{ext.lstrip('.')}"
        blob = self.bucket.blob(object_name)
        blob.upload_from_string(raw_bytes)
        return self._gcs_uri(object_name)

    def upload_page_audio(self, doc_id: str, page_number: int, wav_bytes: bytes) -> str:
        object_name = f"audios/{doc_id}/{page_number}.wav"
        blob = self.bucket.blob(object_name)
        blob.upload_from_string(wav_bytes, content_type="audio/wav")
        return self._gcs_uri(object_name)

    def upload_preview(self, doc_id: str, png_bytes: bytes) -> str:
        object_name = f"previews/{doc_id}.png"
        blob = self.bucket.blob(object_name)
        blob.upload_from_string(png_bytes, content_type="image/png")
        return self._gcs_uri(object_name)

    def download_bytes(self, gcs_uri: str) -> bytes:
        object_name = gcs_uri.split(f"gs://{self.bucket_name}/", 1)[-1]
        blob = self.bucket.blob(object_name)
        return blob.download_as_bytes()

    def signed_url(self, gcs_uri: str, expiration_minutes: int = 60) -> str:
        object_name = gcs_uri.split(f"gs://{self.bucket_name}/", 1)[-1]
        blob = self.bucket.blob(object_name)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )

    def delete_doc_assets(self, doc_id: str, ext: str) -> None:
        doc_object = f"docs/{doc_id}.{ext.lstrip('.')}"
        for object_name in (doc_object, f"previews/{doc_id}.png"):
            try:
                self.bucket.blob(object_name).delete()
            except Exception:
                pass
        for blob in self.client.list_blobs(self.bucket_name, prefix=f"audios/{doc_id}/"):
            try:
                blob.delete()
            except Exception:
                pass
