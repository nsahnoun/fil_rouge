from pathlib import Path
from pydantic_settings import BaseSettings

_HERE = Path(__file__).parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{_HERE}/data/ceph.db"
    secret_key: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    ceph_api_url: str = "http://ceph_api:8000"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = str(_HERE / "data" / "uploads")
    report_dir: str = str(_HERE / "data" / "reports")
    log_dir: str = str(_HERE / "logs")
    clinic_name: str = "Mon Cabinet"
    clinic_city: str = "Paris"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def report_path(self) -> Path:
        return Path(self.report_dir)

    @property
    def log_path(self) -> Path:
        return Path(self.log_dir)

    model_config = {"env_file": str(_HERE / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
