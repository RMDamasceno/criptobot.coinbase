"""
Exceções customizadas para o projeto Crypto Bots.

Este módulo define todas as exceções específicas do sistema,
permitindo tratamento de erros mais granular e informativo.
"""

from typing import Optional, Dict, Any


class CryptoBotsException(Exception):
    """Exceção base para todos os erros do sistema."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class APIException(CryptoBotsException):
    """Exceções relacionadas à API."""
    pass


class CoinbaseAPIException(APIException):
    """Exceções específicas da API Coinbase."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None
    ):
        self.status_code = status_code
        self.response_data = response_data or {}
        self.endpoint = endpoint
        
        details = {
            "status_code": status_code,
            "response_data": response_data,
            "endpoint": endpoint
        }
        
        super().__init__(message, details)


class RateLimitException(CoinbaseAPIException):
    """Exceção para quando o rate limit é excedido."""
    
    def __init__(self, retry_after: Optional[int] = None):
        message = "Rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        
        super().__init__(
            message,
            status_code=429,
            response_data={"retry_after": retry_after}
        )
        self.retry_after = retry_after


class AuthenticationException(CoinbaseAPIException):
    """Exceção para erros de autenticação."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class InsufficientFundsException(CoinbaseAPIException):
    """Exceção para fundos insuficientes."""
    
    def __init__(self, required_amount: Optional[float] = None, available_amount: Optional[float] = None):
        message = "Insufficient funds"
        if required_amount and available_amount:
            message += f". Required: {required_amount}, Available: {available_amount}"
        
        details = {
            "required_amount": required_amount,
            "available_amount": available_amount
        }
        
        super().__init__(message, response_data=details)


class TradingException(CryptoBotsException):
    """Exceções relacionadas ao trading."""
    pass


class InvalidOrderException(TradingException):
    """Exceção para ordens inválidas."""
    
    def __init__(self, message: str, order_data: Optional[Dict[str, Any]] = None):
        super().__init__(message, details={"order_data": order_data})


class PositionNotFoundException(TradingException):
    """Exceção quando uma posição não é encontrada."""
    
    def __init__(self, position_id: str):
        message = f"Position not found: {position_id}"
        super().__init__(message, details={"position_id": position_id})


class RiskManagementException(TradingException):
    """Exceções relacionadas à gestão de risco."""
    pass


class MaxPositionsExceededException(RiskManagementException):
    """Exceção quando o número máximo de posições é excedido."""
    
    def __init__(self, current_positions: int, max_positions: int):
        message = f"Maximum positions exceeded. Current: {current_positions}, Max: {max_positions}"
        super().__init__(
            message,
            details={
                "current_positions": current_positions,
                "max_positions": max_positions
            }
        )


class RiskLimitExceededException(RiskManagementException):
    """Exceção quando o limite de risco é excedido."""
    
    def __init__(self, risk_amount: float, max_risk: float):
        message = f"Risk limit exceeded. Risk: {risk_amount}%, Max: {max_risk}%"
        super().__init__(
            message,
            details={
                "risk_amount": risk_amount,
                "max_risk": max_risk
            }
        )


class SignalException(CryptoBotsException):
    """Exceções relacionadas aos sinais."""
    pass


class InvalidIndicatorException(SignalException):
    """Exceção para indicadores inválidos."""
    
    def __init__(self, indicator_name: str, reason: str):
        message = f"Invalid indicator '{indicator_name}': {reason}"
        super().__init__(message, details={"indicator_name": indicator_name, "reason": reason})


class InsufficientDataException(SignalException):
    """Exceção quando não há dados suficientes para análise."""
    
    def __init__(self, required_periods: int, available_periods: int):
        message = f"Insufficient data. Required: {required_periods}, Available: {available_periods}"
        super().__init__(
            message,
            details={
                "required_periods": required_periods,
                "available_periods": available_periods
            }
        )


class DataException(CryptoBotsException):
    """Exceções relacionadas aos dados."""
    pass


class DataSourceException(DataException):
    """Exceção para problemas com fonte de dados."""
    
    def __init__(self, source: str, message: str):
        full_message = f"Data source '{source}' error: {message}"
        super().__init__(full_message, details={"source": source})


class DataValidationException(DataException):
    """Exceção para dados inválidos."""
    
    def __init__(self, field: str, value: Any, expected_type: str):
        message = f"Invalid data for field '{field}'. Got {type(value).__name__}, expected {expected_type}"
        super().__init__(
            message,
            details={
                "field": field,
                "value": value,
                "expected_type": expected_type
            }
        )


class ConfigurationException(CryptoBotsException):
    """Exceções relacionadas à configuração."""
    pass


class MissingConfigurationException(ConfigurationException):
    """Exceção para configurações obrigatórias ausentes."""
    
    def __init__(self, config_key: str):
        message = f"Missing required configuration: {config_key}"
        super().__init__(message, details={"config_key": config_key})


class InvalidConfigurationException(ConfigurationException):
    """Exceção para configurações inválidas."""
    
    def __init__(self, config_key: str, value: Any, reason: str):
        message = f"Invalid configuration for '{config_key}': {reason}"
        super().__init__(
            message,
            details={
                "config_key": config_key,
                "value": value,
                "reason": reason
            }
        )


class WebSocketException(CryptoBotsException):
    """Exceções relacionadas ao WebSocket."""
    pass


class WebSocketConnectionException(WebSocketException):
    """Exceção para problemas de conexão WebSocket."""
    
    def __init__(self, reason: str):
        message = f"WebSocket connection failed: {reason}"
        super().__init__(message, details={"reason": reason})


class WebSocketMessageException(WebSocketException):
    """Exceção para problemas com mensagens WebSocket."""
    
    def __init__(self, message_data: Any, reason: str):
        message = f"WebSocket message error: {reason}"
        super().__init__(
            message,
            details={
                "message_data": message_data,
                "reason": reason
            }
        )


class NotificationException(CryptoBotsException):
    """Exceções relacionadas às notificações."""
    pass


class NotificationDeliveryException(NotificationException):
    """Exceção para falhas na entrega de notificações."""
    
    def __init__(self, notification_type: str, reason: str):
        message = f"Failed to deliver {notification_type} notification: {reason}"
        super().__init__(
            message,
            details={
                "notification_type": notification_type,
                "reason": reason
            }
        )

