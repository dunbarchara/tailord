import logging
from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from app.clients.storage_client import StorageClient
from app.config import settings

logger = logging.getLogger(__name__)


class AzureStorageClient(StorageClient):
    def _service(self) -> BlobServiceClient:
        if settings.azure_storage_connection_string:
            # Local dev (Azurite) — connection string takes priority over Managed Identity.
            return BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
        # Production — Managed Identity via DefaultAzureCredential.
        # Requires: Storage Blob Data Contributor + Storage Blob Delegator roles on the account.
        from azure.identity import DefaultAzureCredential

        return BlobServiceClient(
            account_url=f"https://{settings.azure_storage_account_name}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )

    def generate_upload_url(self, key: str, expires_in: int = 300) -> str:
        logger.debug("Generating upload URL for key=%s expires_in=%s", key, expires_in)
        service = self._service()
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(seconds=expires_in)

        if service.url.startswith("http://"):
            # Azurite path — account key SAS (Azurite does not support User Delegation SAS).
            account_key = service.credential.account_key
            sas_token = generate_blob_sas(
                account_name=service.account_name,
                container_name=settings.azure_storage_container,
                blob_name=key,
                account_key=account_key,
                permission=BlobSasPermissions(write=True, create=True),
                expiry=expiry,
            )
            base = service.url.rstrip("/")  # e.g. http://127.0.0.1:10000/devstoreaccount1
            url = f"{base}/{settings.azure_storage_container}/{key}?{sas_token}"
        else:
            # Production path — User Delegation SAS signed by Managed Identity.
            # The delegation key validity window is padded by 5 minutes to avoid
            # clock-skew rejections on the storage service side.
            delegation_key = service.get_user_delegation_key(now, expiry + timedelta(minutes=5))
            sas_token = generate_blob_sas(
                account_name=service.account_name,
                container_name=settings.azure_storage_container,
                blob_name=key,
                user_delegation_key=delegation_key,
                permission=BlobSasPermissions(write=True, create=True),
                expiry=expiry,
            )
            url = f"https://{service.account_name}.blob.core.windows.net/{settings.azure_storage_container}/{key}?{sas_token}"

        logger.debug("Upload URL generated for key=%s", key)
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
