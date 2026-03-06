from abc import ABC, abstractmethod

from app.config import settings


class StorageClient(ABC):
    @abstractmethod
    def generate_upload_url(self, key: str, expires_in: int = 300) -> str: ...

    @abstractmethod
    def download_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def delete_object(self, key: str) -> None: ...


def get_storage_client() -> StorageClient:
    if settings.storage_provider == "azure":
        from app.clients.storage_azure import AzureStorageClient
        return AzureStorageClient()
    from app.clients.storage_aws import S3StorageClient
    return S3StorageClient()
