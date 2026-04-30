"""
Core configuration module
Load settings from environment variables using Pydantic Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import json


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # ============================================
    # APPLICATION
    # ============================================
    app_name: str = "Smart Home IoT"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = True
    
    # ============================================
    # DATABASE
    # ============================================
    database_url: str
    db_pool_size: int = 12
    db_max_overflow: int = 0
    db_pool_pre_ping: bool = True
    
    # ============================================
    # JWT AUTHENTICATION
    # ============================================
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    
    # ============================================
    # SUPER ADMIN
    # ============================================
    super_admin_email: str
    super_admin_password: str
    super_admin_name: str = "System Administrator"
    
    # ============================================
    # MQTT BROKER
    # ============================================
    mqtt_broker_host: str
    mqtt_broker_port: int = 8883
    mqtt_username: str
    mqtt_password: str
    mqtt_use_tls: bool = True
    mqtt_client_id: str = "smarthome_backend"
    
    # ============================================
    # SUPABASE STORAGE
    # ============================================
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    storage_bucket_firmwares: str = "firmwares"
    storage_bucket_access_logs: str = "access-logs"
    
    # ============================================
    # SENDGRID EMAIL
    # ============================================
    sendgrid_api_key: str
    sendgrid_from_email: str
    sendgrid_from_name: str = "Smart Home"
    
    # ============================================
    # SECURITY
    # ============================================
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60
    
    # ============================================
    # CORS
    # ============================================
    cors_origins: str = '["http://localhost:3000"]'
    
    @field_validator("cors_origins", mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from JSON string"""
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    # ============================================
    # BACKGROUND WORKERS
    # ============================================
    timer_check_interval: int = 1  # seconds
    cleanup_cron_hour: int = 3
    cleanup_cron_minute: int = 0
    downsample_cron_hour: int = 4
    downsample_cron_minute: int = 0
    retention_days_device_history: int = 7
    retention_days_sensor_data: int = 7
    retention_days_access_logs: int = 7
    
    # ============================================
    # BOARD SETTINGS
    # ============================================
    board_offline_timeout: int = 180  # 3 minutes
    board_pairing_timeout: int = 60  # 60 seconds
    
    # ============================================
    # LOGGING
    # ============================================
    log_level: str = "INFO"
    log_format: str = "json"
    
    # ============================================
    # DEVELOPMENT
    # ============================================
    auto_reload: bool = True
    sql_echo: bool = False


# Global settings instance
settings = Settings()


# Helper functions
def get_settings() -> Settings:
    """
    Dependency injection for FastAPI endpoints
    """
    return settings


def is_production() -> bool:
    """Check if running in production"""
    return settings.environment == "production"


def is_development() -> bool:
    """Check if running in development"""
    return settings.environment == "development"