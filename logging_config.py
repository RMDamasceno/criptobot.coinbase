"""
Configuração de logging para o projeto Crypto Bots.

Este módulo configura o sistema de logging estruturado usando structlog,
com suporte a diferentes níveis de log e formatação adequada para
desenvolvimento e produção.
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory

from .settings import get_settings


def configure_logging() -> None:
    """Configura o sistema de logging estruturado."""
    settings = get_settings()
    
    # Criar diretório de logs se não existir
    log_dir = Path(settings.data_storage_path) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configuração do logging padrão do Python
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=False),
                "foreign_pre_chain": [
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.add_logger_name,
                    structlog.processors.TimeStamper(fmt="iso"),
                ],
            },
            "console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
                "foreign_pre_chain": [
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.add_logger_name,
                    structlog.processors.TimeStamper(fmt="iso"),
                ],
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "console",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.log_level,
                "formatter": "json",
                "filename": str(log_dir / "crypto_bots.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": str(log_dir / "errors.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "trading_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": str(log_dir / "trading.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf8",
            },
            "signals_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": str(log_dir / "signals.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file", "error_file"],
                "level": settings.log_level,
                "propagate": False,
            },
            "crypto_bots.trading": {
                "handlers": ["console", "trading_file", "error_file"],
                "level": settings.log_level,
                "propagate": False,
            },
            "crypto_bots.signals": {
                "handlers": ["console", "signals_file", "error_file"],
                "level": settings.log_level,
                "propagate": False,
            },
            "coinbase": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
            "websockets": {
                "handlers": ["file"],
                "level": "WARNING",
                "propagate": False,
            },
            "urllib3": {
                "handlers": ["file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
    
    # Aplicar configuração
    logging.config.dictConfig(logging_config)
    
    # Configurar structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Retorna um logger estruturado para o módulo especificado.
    
    Args:
        name: Nome do módulo/componente
        
    Returns:
        Logger estruturado configurado
    """
    return structlog.get_logger(name)


def log_trade_execution(
    logger: structlog.stdlib.BoundLogger,
    action: str,
    symbol: str,
    quantity: float,
    price: float,
    order_id: str = None,
    **kwargs: Any
) -> None:
    """
    Log estruturado para execução de trades.
    
    Args:
        logger: Logger estruturado
        action: Ação executada (buy, sell, cancel)
        symbol: Par de trading
        quantity: Quantidade
        price: Preço
        order_id: ID da ordem
        **kwargs: Campos adicionais
    """
    logger.info(
        "Trade executed",
        action=action,
        symbol=symbol,
        quantity=quantity,
        price=price,
        order_id=order_id,
        **kwargs
    )


def log_signal_generated(
    logger: structlog.stdlib.BoundLogger,
    signal_type: str,
    symbol: str,
    strength: float,
    indicators: Dict[str, Any],
    **kwargs: Any
) -> None:
    """
    Log estruturado para geração de sinais.
    
    Args:
        logger: Logger estruturado
        signal_type: Tipo do sinal (buy, sell, hold)
        symbol: Par de trading
        strength: Força do sinal (0-1)
        indicators: Valores dos indicadores
        **kwargs: Campos adicionais
    """
    logger.info(
        "Signal generated",
        signal_type=signal_type,
        symbol=symbol,
        strength=strength,
        indicators=indicators,
        **kwargs
    )


def log_api_request(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    endpoint: str,
    status_code: int = None,
    response_time: float = None,
    error: str = None,
    **kwargs: Any
) -> None:
    """
    Log estruturado para requisições da API.
    
    Args:
        logger: Logger estruturado
        method: Método HTTP
        endpoint: Endpoint da API
        status_code: Código de status da resposta
        response_time: Tempo de resposta em segundos
        error: Mensagem de erro, se houver
        **kwargs: Campos adicionais
    """
    if error:
        logger.error(
            "API request failed",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time=response_time,
            error=error,
            **kwargs
        )
    else:
        logger.info(
            "API request completed",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time=response_time,
            **kwargs
        )


def log_performance_metrics(
    logger: structlog.stdlib.BoundLogger,
    component: str,
    operation: str,
    duration: float,
    success: bool = True,
    **kwargs: Any
) -> None:
    """
    Log estruturado para métricas de performance.
    
    Args:
        logger: Logger estruturado
        component: Componente do sistema
        operation: Operação executada
        duration: Duração em segundos
        success: Se a operação foi bem-sucedida
        **kwargs: Campos adicionais
    """
    logger.info(
        "Performance metric",
        component=component,
        operation=operation,
        duration=duration,
        success=success,
        **kwargs
    )


# Configurar logging na importação do módulo
configure_logging()

