import logging
from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from app.clients.storage_client import StorageClient
from app.config import settings

logger = logging.getLogger(__name__)


class AzureStorageClient(StorageClient):
    def _service(self) -> BlobServiceClient:
        return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)

    def generate_upload_url(self, key: str, expires_in: int = 300) -> str:
        logger.debug("Generating SAS upload URL for key=%s expires_in=%s", key, expires_in)
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
        url = f"https://{account_name}.blob.core.windows.net/{settings.azure_storage_container}/{key}?{sas_token}"
        logger.debug("SAS URL generated for key=%s", key)
        return url

    def download_bytes(self, key: str) -> bytes:
        logger.debug("Downloading blob key=%s container=%s", key, settings.azure_storage_container)
        client = self._service().get_blob_client(settings.azure_storage_container, key)
        data = client.download_blob().readall()
        logger.debug("Downloaded %d bytes for key=%s", len(data), key)
        return data

    def delete_object(self, key: str) -> None:
        logger.debug("Deleting blob key=%s container=%s", key, settings.azure_storage_container)
        client = self._service().get_blob_client(settings.azure_storage_container, key)
        client.delete_blob()
        logger.debug("Deleted blob key=%s", key)
