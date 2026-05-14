"""
Storage abstraction layer.

All app code must interact with storage through StorageClient — never import
azure.storage or boto3 directly outside of storage_azure.py and storage_aws.py.

Provider is selected at runtime via settings.storage_provider ("azure" | "aws").
Both provider implementations are kept as dependencies so the same Docker image
runs on either cloud without code changes (see CLAUDE.md § Cloud Portability).
"""

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
    if settings.storage_provider == "aws":
        from app.clients.storage_aws import S3StorageClient

        return S3StorageClient()
    from app.clients.storage_azure import AzureStorageClient

    return AzureStorageClient()
