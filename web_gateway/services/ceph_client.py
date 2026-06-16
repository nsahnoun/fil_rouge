import logging
from pathlib import Path

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


_override_url: str | None = None


def ceph_client_override_url(url: str):
    global _override_url
    _override_url = url


def _get_ceph_url() -> str:
    return _override_url or settings.ceph_api_url


class CephClient:
    def __init__(self):
        self.timeout = 120.0

    @property
    def base_url(self):
        return _get_ceph_url()

    async def predict(self, image_path: str | Path) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(image_path, "rb") as f:
                    files = {"file": (Path(image_path).name, f, "image/png")}
                    resp = await client.post(f"{self.base_url}/predict", files=files)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Erreur appel ceph_api /predict: {e}")
            return None

    async def health(self) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.json() if resp.is_success else None
        except Exception as e:
            logger.warning(f"ceph_api health check failed: {e}")
            return None
