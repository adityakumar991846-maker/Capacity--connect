import json
import posixpath
import urllib.request
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core.files.storage import Storage
from django.core.files.utils import validate_file_name


class SupabaseStorage(Storage):
    """
    Django storage backend using the Supabase Storage REST API.

    Uses the Supabase service-role key on the backend only.
    """

    def __init__(self, bucket=None, supabase_url=None, service_role_key=None):
        self.bucket = bucket or getattr(
            settings, "SUPABASE_STORAGE_BUCKET", "capacity-media"
        )

        self.supabase_url = (
            supabase_url or getattr(settings, "SUPABASE_URL", "")
        ).rstrip("/")

        self.service_role_key = (
            service_role_key
            if service_role_key is not None
            else getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
        )

    def _clean_name(self, name):
        """Normalize and validate uploaded file paths."""
        name = name.replace("\\", "/").lstrip("/")
        name = posixpath.normpath(name)

        if name == "." or name.startswith("../") or "/../" in name:
            raise ValueError("Invalid storage path")

        return validate_file_name(name, allow_relative_path=True)

    def _object_url(self, name):
        """Return the Supabase Storage object API URL."""
        name = self._clean_name(name)

        return (
            f"{self.supabase_url}/storage/v1/object/"
            f"{self.bucket}/{name}"
        )

    def _get_headers(self, content_type=None):
        """Build Supabase service-role authentication headers."""
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }

        if content_type:
            headers["Content-Type"] = content_type

        return headers

    # Backward-compatible internal method name.
    def _headers(self, content_type=None):
        return self._get_headers(content_type)

    def _save(self, name, content):
        """Upload a Django File to Supabase Storage."""
        name = self._clean_name(name)

        content_type = getattr(content, "content_type", None)
        if not content_type:
            content_type = "application/octet-stream"

        if hasattr(content, "chunks"):
            data = b"".join(content.chunks())
        else:
            data = content.read()

        headers = self._get_headers(content_type)
        headers["X-upsert"] = "true"

        request = urllib.request.Request(
            self._object_url(name),
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)

                if not isinstance(status, int):
                    status = 200

                if status not in (200, 201):
                    raise IOError(
                        f"Failed to upload '{name}': HTTP {status}"
                    )

        except (HTTPError, URLError, OSError) as exc:
            raise IOError(
                f"Failed to upload '{name}': {exc}"
            ) from exc

        return name

    def _open(self, name, mode="rb"):
        """Open a file from Supabase Storage."""
        if "r" not in mode:
            raise ValueError(
                "SupabaseStorage only supports reading files."
            )

        request = urllib.request.Request(
            self._object_url(name),
            headers=self._get_headers(),
            method="GET",
        )

        try:
            response = urllib.request.urlopen(request, timeout=30)

            from django.core.files.base import ContentFile

            return ContentFile(
                response.read(),
                name=self._clean_name(name),
            )

        except (HTTPError, URLError, OSError) as exc:
            raise IOError(
                f"Unable to open Supabase Storage object '{name}': {exc}"
            ) from exc

    def exists(self, name):
        """Return True if an object exists."""
        request = urllib.request.Request(
            self._object_url(name),
            headers=self._get_headers(),
            method="HEAD",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)

                if not isinstance(status, int):
                    status = 200

                return 200 <= status < 300

        except HTTPError as exc:
            if exc.code == 404:
                return False

            raise IOError(
                f"Supabase Storage existence check failed: {exc}"
            ) from exc

        except (URLError, OSError) as exc:
            raise IOError(
                f"Supabase Storage existence check failed: {exc}"
            ) from exc

    def delete(self, name):
        """Delete an object from Supabase Storage."""
        request = urllib.request.Request(
            self._object_url(name),
            data=b"",
            headers=self._get_headers("application/json"),
            method="DELETE",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)

                if not isinstance(status, int):
                    status = 200

                return status in (200, 204)

        except HTTPError as exc:
            if exc.code == 404:
                return False

            raise IOError(
                f"Supabase Storage delete failed: {exc}"
            ) from exc

        except (URLError, OSError) as exc:
            raise IOError(
                f"Supabase Storage delete failed: {exc}"
            ) from exc

    def size(self, name):
        """Return object size from Supabase Storage metadata."""
        request = urllib.request.Request(
            self._object_url(name),
            headers=self._get_headers(),
            method="HEAD",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:

                # Normal Supabase response.
                content_length = response.headers.get("Content-Length")

                # Only use real string/bytes header values.
                # This also keeps mocked responses working correctly.
                if isinstance(content_length, (str, bytes)):
                    try:
                        return int(content_length)
                    except (ValueError, TypeError):
                        pass

                # Some API/test responses provide JSON metadata.
                body = response.read()

                if isinstance(body, bytes):
                    body = body.decode("utf-8")

                if isinstance(body, str) and body.strip():
                    metadata = json.loads(body)

                    if "size" in metadata:
                        return int(metadata["size"])

                raise IOError(
                    f"Supabase Storage did not return object size "
                    f"for '{name}'"
                )

        except HTTPError as exc:
            raise IOError(
                f"Supabase Storage size check failed: {exc}"
            ) from exc

        except (URLError, OSError, ValueError, TypeError) as exc:
            raise IOError(
                f"Supabase Storage size check failed: {exc}"
            ) from exc

        except json.JSONDecodeError as exc:
            raise IOError(
                f"Supabase Storage size check failed: {exc}"
            ) from exc

    def url(self, name):
        """Return the public Supabase Storage URL."""
        name = self._clean_name(name)

        return (
            f"{self.supabase_url}/storage/v1/object/public/"
            f"{self.bucket}/{name}"
        )