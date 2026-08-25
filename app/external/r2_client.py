import aioboto3

from app.core.conf import settings


class R2Client:
    def __init__(self):
        self._session = aioboto3.Session()

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key
        )

    async def upload_file(self, object_key: str, file_bytes: bytes, content_type: str) -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket = settings.r2_bucket_name,
                Key = object_key,
                Body = file_bytes,
                ContentType = content_type
            )

    async def download_file(self, object_key: str) -> bytes:
        async with self._client() as client:
            response = await client.get_object(Bucket=settings.r2_bucket_name, Key=object_key)
            return await response['Body'].read()

    async def delete_file(self, object_key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=settings.r2_bucket_name, Key=object_key)

r2_client = R2Client()