"""
Rate Limiter para controle de requisições à API.

Este módulo implementa um sistema de rate limiting para respeitar
os limites da API Coinbase e evitar erros 429 (Too Many Requests).
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
from threading import Lock

from ..config.logging_config import get_logger
from .exceptions import RateLimitException

logger = get_logger(__name__)


@dataclass
class RateLimitInfo:
    """Informações sobre rate limiting."""
    requests_per_second: float
    requests_per_minute: float
    requests_per_hour: float
    window_start: float
    request_count: int
    last_request_time: float


class RateLimiter:
    """
    Rate limiter thread-safe para controle de requisições.
    
    Implementa sliding window rate limiting com suporte a múltiplas
    janelas de tempo (segundo, minuto, hora).
    """
    
    def __init__(
        self,
        requests_per_second: float = 30.0,
        requests_per_minute: float = 1800.0,
        requests_per_hour: float = 10000.0,
        burst_allowance: int = 5
    ):
        """
        Inicializa o rate limiter.
        
        Args:
            requests_per_second: Máximo de requests por segundo
            requests_per_minute: Máximo de requests por minuto
            requests_per_hour: Máximo de requests por hora
            burst_allowance: Allowance para rajadas de requests
        """
        self.requests_per_second = requests_per_second
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_allowance = burst_allowance
        
        # Janelas de tempo para tracking
        self.second_window: Dict[int, int] = {}
        self.minute_window: Dict[int, int] = {}
        self.hour_window: Dict[int, int] = {}
        
        # Controle de burst
        self.burst_tokens = burst_allowance
        self.last_token_refill = time.time()
        
        # Thread safety
        self._lock = Lock()
        
        logger.info(
            "Rate limiter initialized",
            rps=requests_per_second,
            rpm=requests_per_minute,
            rph=requests_per_hour,
            burst=burst_allowance
        )
    
    def can_make_request(self) -> bool:
        """
        Verifica se uma requisição pode ser feita agora.
        
        Returns:
            True se a requisição pode ser feita, False caso contrário
        """
        with self._lock:
            current_time = time.time()
            current_second = int(current_time)
            current_minute = int(current_time // 60)
            current_hour = int(current_time // 3600)
            
            # Limpar janelas antigas
            self._cleanup_windows(current_second, current_minute, current_hour)
            
            # Verificar limites
            second_count = self.second_window.get(current_second, 0)
            minute_count = sum(self.minute_window.values())
            hour_count = sum(self.hour_window.values())
            
            # Verificar se pode fazer a requisição
            if second_count >= self.requests_per_second:
                return False
            
            if minute_count >= self.requests_per_minute:
                return False
            
            if hour_count >= self.requests_per_hour:
                return False
            
            return True
    
    def wait_if_needed(self) -> Optional[float]:
        """
        Calcula o tempo de espera necessário antes da próxima requisição.
        
        Returns:
            Tempo de espera em segundos, ou None se não precisa esperar
        """
        if self.can_make_request():
            return None
        
        current_time = time.time()
        current_second = int(current_time)
        current_minute = int(current_time // 60)
        current_hour = int(current_time // 3600)
        
        # Calcular tempo de espera baseado no limite mais restritivo
        wait_times = []
        
        # Limite por segundo
        second_count = self.second_window.get(current_second, 0)
        if second_count >= self.requests_per_second:
            wait_times.append(1.0 - (current_time % 1))
        
        # Limite por minuto
        minute_count = sum(self.minute_window.values())
        if minute_count >= self.requests_per_minute:
            wait_times.append(60.0 - (current_time % 60))
        
        # Limite por hora
        hour_count = sum(self.hour_window.values())
        if hour_count >= self.requests_per_hour:
            wait_times.append(3600.0 - (current_time % 3600))
        
        return min(wait_times) if wait_times else None
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Adquire permissão para fazer uma requisição.
        
        Args:
            timeout: Tempo máximo de espera em segundos
            
        Returns:
            True se conseguiu adquirir, False se timeout
            
        Raises:
            RateLimitException: Se não conseguir adquirir dentro do timeout
        """
        start_time = time.time()
        
        while True:
            if self.can_make_request():
                self._record_request()
                return True
            
            wait_time = self.wait_if_needed()
            if wait_time is None:
                self._record_request()
                return True
            
            # Verificar timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise RateLimitException()
            
            # Esperar um pouco antes de tentar novamente
            sleep_time = min(wait_time, 0.1)
            time.sleep(sleep_time)
    
    async def acquire_async(self, timeout: Optional[float] = None) -> bool:
        """
        Versão assíncrona do acquire.
        
        Args:
            timeout: Tempo máximo de espera em segundos
            
        Returns:
            True se conseguiu adquirir, False se timeout
        """
        start_time = time.time()
        
        while True:
            if self.can_make_request():
                self._record_request()
                return True
            
            wait_time = self.wait_if_needed()
            if wait_time is None:
                self._record_request()
                return True
            
            # Verificar timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise RateLimitException()
            
            # Esperar assincronamente
            sleep_time = min(wait_time, 0.1)
            await asyncio.sleep(sleep_time)
    
    def _record_request(self) -> None:
        """Registra uma requisição nas janelas de tempo."""
        current_time = time.time()
        current_second = int(current_time)
        current_minute = int(current_time // 60)
        current_hour = int(current_time // 3600)
        
        # Incrementar contadores
        self.second_window[current_second] = self.second_window.get(current_second, 0) + 1
        self.minute_window[current_minute] = self.minute_window.get(current_minute, 0) + 1
        self.hour_window[current_hour] = self.hour_window.get(current_hour, 0) + 1
        
        logger.debug(
            "Request recorded",
            second=current_second,
            minute=current_minute,
            hour=current_hour,
            second_count=self.second_window[current_second],
            minute_count=self.minute_window[current_minute],
            hour_count=self.hour_window[current_hour]
        )
    
    def _cleanup_windows(self, current_second: int, current_minute: int, current_hour: int) -> None:
        """Remove entradas antigas das janelas de tempo."""
        # Limpar janela de segundos (manter apenas último segundo)
        old_seconds = [s for s in self.second_window.keys() if s < current_second - 1]
        for s in old_seconds:
            del self.second_window[s]
        
        # Limpar janela de minutos (manter apenas últimos 2 minutos)
        old_minutes = [m for m in self.minute_window.keys() if m < current_minute - 2]
        for m in old_minutes:
            del self.minute_window[m]
        
        # Limpar janela de horas (manter apenas últimas 2 horas)
        old_hours = [h for h in self.hour_window.keys() if h < current_hour - 2]
        for h in old_hours:
            del self.hour_window[h]
    
    def get_status(self) -> RateLimitInfo:
        """
        Retorna informações sobre o status atual do rate limiter.
        
        Returns:
            Informações sobre rate limiting
        """
        with self._lock:
            current_time = time.time()
            current_second = int(current_time)
            current_minute = int(current_time // 60)
            current_hour = int(current_time // 3600)
            
            self._cleanup_windows(current_second, current_minute, current_hour)
            
            second_count = self.second_window.get(current_second, 0)
            minute_count = sum(self.minute_window.values())
            hour_count = sum(self.hour_window.values())
            
            return RateLimitInfo(
                requests_per_second=second_count,
                requests_per_minute=minute_count,
                requests_per_hour=hour_count,
                window_start=current_time,
                request_count=hour_count,
                last_request_time=current_time
            )
    
    def reset(self) -> None:
        """Reseta todos os contadores do rate limiter."""
        with self._lock:
            self.second_window.clear()
            self.minute_window.clear()
            self.hour_window.clear()
            self.burst_tokens = self.burst_allowance
            self.last_token_refill = time.time()
            
            logger.info("Rate limiter reset")


# Instância global do rate limiter
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Retorna a instância global do rate limiter.
    
    Returns:
        Instância do rate limiter
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        from ..config.settings import get_settings
        settings = get_settings()
        
        _global_rate_limiter = RateLimiter(
            requests_per_second=settings.max_requests_per_second,
            requests_per_minute=settings.max_requests_per_second * 60,
            requests_per_hour=10000  # Limite da Coinbase
        )
    
    return _global_rate_limiter


def reset_rate_limiter() -> None:
    """Reseta o rate limiter global."""
    global _global_rate_limiter
    if _global_rate_limiter:
        _global_rate_limiter.reset()

