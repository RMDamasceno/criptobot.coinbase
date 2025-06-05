"""
Configurações principais do projeto Crypto Bots.

Este módulo centraliza todas as configurações do sistema, incluindo:
- Configurações da API Coinbase
- Parâmetros dos bots
- Configurações de trading
- Configurações de notificações
- Configurações de logging
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from enum import Enum


class Environment(str, Enum):
    """Ambientes disponíveis."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class BotMode(str, Enum):
    """Modos de operação do bot."""
    SIGNALS = "signals"
    TRADING = "trading"
    COMBINED = "combined"


class NotificationLevel(str, Enum):
    """Níveis de notificação."""
    ALL = "all"
    IMPORTANT = "important"
    CRITICAL = "critical"


class Settings(BaseSettings):
    """Configurações principais do sistema."""
    
    # =============================================================================
    # COINBASE API CONFIGURATION
    # =============================================================================
    
    coinbase_api_key: str = Field(..., env="COINBASE_API_KEY")
    coinbase_api_secret: str = Field(..., env="COINBASE_API_SECRET")
    coinbase_environment: Environment = Field(Environment.SANDBOX, env="COINBASE_ENVIRONMENT")
    coinbase_timeout: int = Field(30, env="COINBASE_TIMEOUT")
    
    @property
    def coinbase_base_url(self) -> str:
        """URL base da API Coinbase baseada no ambiente."""
        if self.coinbase_environment == Environment.SANDBOX:
            return "https://api-sandbox.coinbase.com"
        return "https://api.coinbase.com"
    
    # =============================================================================
    # BOT CONFIGURATION
    # =============================================================================
    
    bot_mode: BotMode = Field(BotMode.SIGNALS, env="BOT_MODE")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    data_storage_path: str = Field("./data", env="DATA_STORAGE_PATH")
    
    # Update intervals (seconds)
    signal_update_interval: int = Field(60, env="SIGNAL_UPDATE_INTERVAL")
    trading_update_interval: int = Field(30, env="TRADING_UPDATE_INTERVAL")
    market_data_interval: int = Field(5, env="MARKET_DATA_INTERVAL")
    
    # =============================================================================
    # TRADING CONFIGURATION
    # =============================================================================
    
    default_portfolio: Optional[str] = Field(None, env="DEFAULT_PORTFOLIO")
    
    # Risk Management
    risk_percentage: float = Field(2.0, env="RISK_PERCENTAGE")
    max_positions: int = Field(5, env="MAX_POSITIONS")
    max_daily_loss: float = Field(5.0, env="MAX_DAILY_LOSS")
    
    # Position Sizing
    default_position_size: float = Field(100.0, env="DEFAULT_POSITION_SIZE")
    min_position_size: float = Field(10.0, env="MIN_POSITION_SIZE")
    max_position_size: float = Field(1000.0, env="MAX_POSITION_SIZE")
    
    # Stop Loss and Take Profit
    default_stop_loss: float = Field(2.0, env="DEFAULT_STOP_LOSS")
    default_take_profit: float = Field(4.0, env="DEFAULT_TAKE_PROFIT")
    
    # Trading Pairs
    trading_pairs_str: str = Field("BTC-USD,ETH-USD,ADA-USD,SOL-USD", env="TRADING_PAIRS")
    
    @property
    def trading_pairs(self) -> List[str]:
        """Lista de pares de trading."""
        return [pair.strip() for pair in self.trading_pairs_str.split(",")]
    
    # =============================================================================
    # SIGNAL CONFIGURATION
    # =============================================================================
    
    # Technical Indicators
    rsi_period: int = Field(14, env="RSI_PERIOD")
    rsi_overbought: float = Field(70, env="RSI_OVERBOUGHT")
    rsi_oversold: float = Field(30, env="RSI_OVERSOLD")
    
    macd_fast: int = Field(12, env="MACD_FAST")
    macd_slow: int = Field(26, env="MACD_SLOW")
    macd_signal: int = Field(9, env="MACD_SIGNAL")
    
    bb_period: int = Field(20, env="BB_PERIOD")
    bb_std: float = Field(2, env="BB_STD")
    
    ma_short: int = Field(10, env="MA_SHORT")
    ma_long: int = Field(50, env="MA_LONG")
    
    # Signal Thresholds
    signal_strength_threshold: float = Field(0.7, env="SIGNAL_STRENGTH_THRESHOLD")
    min_volume_threshold: float = Field(1000000, env="MIN_VOLUME_THRESHOLD")
    
    # =============================================================================
    # NOTIFICATION CONFIGURATION
    # =============================================================================
    
    notification_level: NotificationLevel = Field(NotificationLevel.IMPORTANT, env="NOTIFICATION_LEVEL")
    
    # Console Notifications
    enable_console_notifications: bool = Field(True, env="ENABLE_CONSOLE_NOTIFICATIONS")
    
    # File Notifications
    enable_file_notifications: bool = Field(True, env="ENABLE_FILE_NOTIFICATIONS")
    notification_file_path: str = Field("./data/signals/notifications.log", env="NOTIFICATION_FILE_PATH")
    
    # Webhook Notifications
    enable_webhook_notifications: bool = Field(False, env="ENABLE_WEBHOOK_NOTIFICATIONS")
    webhook_url: Optional[str] = Field(None, env="WEBHOOK_URL")
    
    # Slack Notifications
    enable_slack_notifications: bool = Field(False, env="ENABLE_SLACK_NOTIFICATIONS")
    slack_bot_token: Optional[str] = Field(None, env="SLACK_BOT_TOKEN")
    slack_channel: str = Field("#crypto-signals", env="SLACK_CHANNEL")
    
    # Discord Notifications
    enable_discord_notifications: bool = Field(False, env="ENABLE_DISCORD_NOTIFICATIONS")
    discord_webhook_url: Optional[str] = Field(None, env="DISCORD_WEBHOOK_URL")
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    
    database_type: str = Field("sqlite", env="DATABASE_TYPE")
    database_url: str = Field("sqlite:///./data/crypto_bots.db", env="DATABASE_URL")
    
    # Redis
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    enable_redis_cache: bool = Field(False, env="ENABLE_REDIS_CACHE")
    
    # =============================================================================
    # MONITORING AND PERFORMANCE
    # =============================================================================
    
    # Prometheus
    enable_prometheus_metrics: bool = Field(False, env="ENABLE_PROMETHEUS_METRICS")
    prometheus_port: int = Field(8000, env="PROMETHEUS_PORT")
    
    # Performance
    enable_async_processing: bool = Field(True, env="ENABLE_ASYNC_PROCESSING")
    max_concurrent_requests: int = Field(10, env="MAX_CONCURRENT_REQUESTS")
    request_retry_attempts: int = Field(3, env="REQUEST_RETRY_ATTEMPTS")
    request_retry_delay: float = Field(1.0, env="REQUEST_RETRY_DELAY")
    
    # =============================================================================
    # DEVELOPMENT AND DEBUGGING
    # =============================================================================
    
    debug_mode: bool = Field(False, env="DEBUG_MODE")
    dry_run_mode: bool = Field(True, env="DRY_RUN_MODE")
    
    # Backtesting
    enable_backtesting: bool = Field(False, env="ENABLE_BACKTESTING")
    backtest_start_date: str = Field("2024-01-01", env="BACKTEST_START_DATE")
    backtest_end_date: str = Field("2024-12-31", env="BACKTEST_END_DATE")
    
    # =============================================================================
    # SECURITY
    # =============================================================================
    
    # Rate Limiting
    enable_rate_limiting: bool = Field(True, env="ENABLE_RATE_LIMITING")
    max_requests_per_second: int = Field(30, env="MAX_REQUESTS_PER_SECOND")
    
    # IP Whitelist
    ip_whitelist_str: str = Field("", env="IP_WHITELIST")
    
    @property
    def ip_whitelist(self) -> List[str]:
        """Lista de IPs permitidos."""
        if not self.ip_whitelist_str:
            return []
        return [ip.strip() for ip in self.ip_whitelist_str.split(",")]
    
    ssl_verify: bool = Field(True, env="SSL_VERIFY")
    
    # =============================================================================
    # VALIDATORS
    # =============================================================================
    
    @field_validator("risk_percentage")
    @classmethod
    def validate_risk_percentage(cls, v):
        if not 0.1 <= v <= 10.0:
            raise ValueError("Risk percentage must be between 0.1% and 10%")
        return v
    
    @field_validator("max_positions")
    @classmethod
    def validate_max_positions(cls, v):
        if not 1 <= v <= 20:
            raise ValueError("Max positions must be between 1 and 20")
        return v
    
    @field_validator("signal_strength_threshold")
    @classmethod
    def validate_signal_strength(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Signal strength threshold must be between 0.0 and 1.0")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        frozen = False
        extra = "ignore"


# Instância global das configurações
settings = Settings()


def get_settings() -> Settings:
    """Retorna a instância das configurações."""
    return settings


def reload_settings() -> Settings:
    """Recarrega as configurações do arquivo .env."""
    global settings
    settings = Settings()
    return settings

