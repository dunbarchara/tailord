from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

from app.clients.storage_client import StorageClient
from app.config import settings


class AzureStorageClient(StorageClient):
    def _service(self) -> BlobServiceClient:
        return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)

    def generate_upload_url(self, key: str, expires_in: int = 300) -> str:
        service = self._service()
        account_name = service.account_name
        account_key = service.credential.account_key
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=settings.azure_storage_container,
            blob_name=key,
            account_key=account_key,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )
        return f"https://{account_name}.blob.core.windows.net/{settings.azure_storage_container}/{key}?{sas_token}"

    def download_bytes(self, key: str) -> bytes:
        client = self._service().get_blob_client(settings.azure_storage_container, key)
        return client.download_blob().readall()

    def delete_object(self, key: str) -> None:
        client = self._service().get_blob_client(settings.azure_storage_container, key)
        client.delete_blob()
