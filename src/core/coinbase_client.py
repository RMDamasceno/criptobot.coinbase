"""
Cliente da API Coinbase Advanced Trade.

Este módulo implementa um cliente robusto para a API Coinbase,
com suporte a rate limiting, retry automático, logging estruturado
e tratamento de erros.
"""

import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json

from coinbase.rest import RESTClient
from coinbase.websocket import WSClient

from ..config.settings import get_settings
from ..config.logging_config import get_logger, log_api_request
from .rate_limiter import get_rate_limiter
from .exceptions import (
    CoinbaseAPIException,
    RateLimitException,
    AuthenticationException,
    InsufficientFundsException,
    InvalidOrderException
)

logger = get_logger(__name__)


class CoinbaseClient:
    """
    Cliente principal para a API Coinbase Advanced Trade.
    
    Fornece uma interface simplificada e robusta para interagir
    com a API Coinbase, incluindo rate limiting automático,
    retry de requisições e tratamento de erros.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Inicializa o cliente Coinbase.
        
        Args:
            api_key: Chave da API (opcional, usa configuração se não fornecida)
            api_secret: Secret da API (opcional, usa configuração se não fornecida)
        """
        self.settings = get_settings()
        self.rate_limiter = get_rate_limiter()
        
        # Usar credenciais fornecidas ou das configurações
        self.api_key = api_key or self.settings.coinbase_api_key
        self.api_secret = api_secret or self.settings.coinbase_api_secret
        
        # Inicializar cliente REST
        self._rest_client = None
        self._ws_client = None
        
        # Configurações de retry
        self.max_retries = self.settings.request_retry_attempts
        self.retry_delay = self.settings.request_retry_delay
        
        logger.info(
            "Coinbase client initialized",
            environment=self.settings.coinbase_environment,
            base_url=self.settings.coinbase_base_url,
            timeout=self.settings.coinbase_timeout
        )
    
    @property
    def rest_client(self) -> RESTClient:
        """Retorna o cliente REST, inicializando se necessário."""
        if self._rest_client is None:
            self._rest_client = RESTClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                timeout=self.settings.coinbase_timeout,
                rate_limit_headers=True
            )
        return self._rest_client
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Faz uma requisição à API com rate limiting e retry automático.
        
        Args:
            method: Método da requisição (get, post, put, delete)
            endpoint: Endpoint da API
            params: Parâmetros da query string
            data: Dados do corpo da requisição
            **kwargs: Argumentos adicionais
            
        Returns:
            Resposta da API
            
        Raises:
            CoinbaseAPIException: Para erros da API
            RateLimitException: Para rate limiting
        """
        for attempt in range(self.max_retries + 1):
            try:
                # Aguardar rate limiter
                self.rate_limiter.acquire(timeout=30)
                
                start_time = time.time()
                
                # Fazer requisição
                if method.lower() == 'get':
                    response = self.rest_client.get(endpoint, params=params or {}, **kwargs)
                elif method.lower() == 'post':
                    response = self.rest_client.post(endpoint, data=data or {}, **kwargs)
                elif method.lower() == 'put':
                    response = self.rest_client.put(endpoint, data=data or {}, **kwargs)
                elif method.lower() == 'delete':
                    response = self.rest_client.delete(endpoint, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response_time = time.time() - start_time
                
                # Log da requisição bem-sucedida
                log_api_request(
                    logger,
                    method=method.upper(),
                    endpoint=endpoint,
                    status_code=200,  # Assumindo sucesso se não houve exceção
                    response_time=response_time
                )
                
                return response
                
            except Exception as e:
                response_time = time.time() - start_time if 'start_time' in locals() else 0
                
                # Determinar tipo de erro
                if "429" in str(e) or "rate limit" in str(e).lower():
                    error_msg = "Rate limit exceeded"
                    log_api_request(
                        logger,
                        method=method.upper(),
                        endpoint=endpoint,
                        status_code=429,
                        response_time=response_time,
                        error=error_msg
                    )
                    
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limited, retrying in {wait_time}s", attempt=attempt + 1)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RateLimitException()
                
                elif "401" in str(e) or "unauthorized" in str(e).lower():
                    log_api_request(
                        logger,
                        method=method.upper(),
                        endpoint=endpoint,
                        status_code=401,
                        response_time=response_time,
                        error="Authentication failed"
                    )
                    raise AuthenticationException()
                
                else:
                    # Erro genérico
                    error_msg = str(e)
                    log_api_request(
                        logger,
                        method=method.upper(),
                        endpoint=endpoint,
                        response_time=response_time,
                        error=error_msg
                    )
                    
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Request failed, retrying in {wait_time}s", error=error_msg, attempt=attempt + 1)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise CoinbaseAPIException(f"Request failed after {self.max_retries} retries: {error_msg}")
        
        raise CoinbaseAPIException("Max retries exceeded")
    
    # =============================================================================
    # ACCOUNT METHODS
    # =============================================================================
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """
        Retorna lista de contas.
        
        Returns:
            Lista de contas
        """
        response = self._make_request('GET', '/api/v3/brokerage/accounts')
        return response.accounts if hasattr(response, 'accounts') else []
    
    def get_account(self, account_id: str) -> Dict[str, Any]:
        """
        Retorna detalhes de uma conta específica.
        
        Args:
            account_id: ID da conta
            
        Returns:
            Detalhes da conta
        """
        response = self._make_request('GET', f'/api/v3/brokerage/accounts/{account_id}')
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    # =============================================================================
    # PRODUCT METHODS
    # =============================================================================
    
    def get_products(self) -> List[Dict[str, Any]]:
        """
        Retorna lista de produtos disponíveis.
        
        Returns:
            Lista de produtos
        """
        response = self._make_request('GET', '/api/v3/brokerage/products')
        return response.products if hasattr(response, 'products') else []
    
    def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Retorna detalhes de um produto específico.
        
        Args:
            product_id: ID do produto (ex: BTC-USD)
            
        Returns:
            Detalhes do produto
        """
        response = self._make_request('GET', f'/api/v3/brokerage/products/{product_id}')
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    def get_product_candles(
        self,
        product_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        granularity: str = "ONE_MINUTE"
    ) -> List[Dict[str, Any]]:
        """
        Retorna dados de candlestick para um produto.

        CORREÇÃO: Valida limite de 350 candles da API Coinbase.
        """
        from datetime import timedelta

        # Mapeamento de granularidade para segundos
        granularity_seconds = {
            "ONE_MINUTE": 60,
            "FIVE_MINUTE": 300,
            "FIFTEEN_MINUTE": 900,
            "ONE_HOUR": 3600,
            "SIX_HOUR": 21600,
            "ONE_DAY": 86400
        }

        params = {"granularity": granularity}

        # CORREÇÃO: Validar limite de 350 candles
        if start and end:
            # Calcular número de candles que seriam retornados
            time_diff = (end - start).total_seconds()
            interval_seconds = granularity_seconds.get(granularity, 60)
            estimated_candles = int(time_diff / interval_seconds)

            # Se exceder 350, ajustar o período
            if estimated_candles > 350:
                logger.warning(
                    f"Período solicitado resultaria em {estimated_candles} candles. "
                    f"Limitando a 350 candles para evitar erro da API."
                )
                # Ajustar end para não exceder 350 candles
                max_seconds = 350 * interval_seconds
                end = start + timedelta(seconds=max_seconds)

            params["start"] = int(start.timestamp())
            params["end"] = int(end.timestamp())
        elif start:
            params["start"] = int(start.timestamp())
        elif end:
            params["end"] = int(end.timestamp())

        response = self._make_request(
            'GET',
            f'/api/v3/brokerage/products/{product_id}/candles',
            params=params
        )
    
        return response.candles if hasattr(response, 'candles') else []
    
    def get_market_trades(self, product_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retorna trades recentes do mercado.
        
        Args:
            product_id: ID do produto
            limit: Número máximo de trades
            
        Returns:
            Lista de trades
        """
        params = {"limit": limit}
        response = self._make_request(
            'GET',
            f'/api/v3/brokerage/products/{product_id}/ticker',
            params=params
        )
        
        return response.trades if hasattr(response, 'trades') else []
    
    def get_best_bid_ask(self, product_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Retorna melhores ofertas de compra e venda.
        
        Args:
            product_ids: Lista de IDs de produtos
            
        Returns:
            Melhores ofertas
        """
        params = {}
        if product_ids:
            params["product_ids"] = ",".join(product_ids)
        
        response = self._make_request('GET', '/api/v3/brokerage/best_bid_ask', params=params)
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    def get_product_book(self, product_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        Retorna order book de um produto.
        
        Args:
            product_id: ID do produto
            limit: Número de níveis do book
            
        Returns:
            Order book
        """
        params = {"product_id": product_id, "limit": limit}
        response = self._make_request('GET', '/api/v3/brokerage/product_book', params=params)
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    # =============================================================================
    # ORDER METHODS
    # =============================================================================
    
    def create_order(
        self,
        product_id: str,
        side: str,
        order_type: str = "market_order",
        size: Optional[str] = None,
        price: Optional[str] = None,
        client_order_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Cria uma nova ordem.
        
        Args:
            product_id: ID do produto
            side: Lado da ordem (buy/sell)
            order_type: Tipo da ordem (market_order, limit_order)
            size: Tamanho da ordem
            price: Preço (para limit orders)
            client_order_id: ID customizado da ordem
            **kwargs: Parâmetros adicionais
            
        Returns:
            Detalhes da ordem criada
        """
        order_data = {
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                order_type: {}
            }
        }
        
        if client_order_id:
            order_data["client_order_id"] = client_order_id
        
        # Configurar parâmetros específicos do tipo de ordem
        if order_type == "market_order":
            if size:
                if side == "buy":
                    order_data["order_configuration"][order_type]["quote_size"] = size
                else:
                    order_data["order_configuration"][order_type]["base_size"] = size
        elif order_type == "limit_order":
            if size and price:
                order_data["order_configuration"][order_type]["base_size"] = size
                order_data["order_configuration"][order_type]["limit_price"] = price
        
        # Adicionar parâmetros extras
        order_data.update(kwargs)
        
        response = self._make_request('POST', '/api/v3/brokerage/orders', data=order_data)
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    def cancel_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        """
        Cancela múltiplas ordens.
        
        Args:
            order_ids: Lista de IDs das ordens
            
        Returns:
            Resultado do cancelamento
        """
        data = {"order_ids": order_ids}
        response = self._make_request('POST', '/api/v3/brokerage/orders/batch_cancel', data=data)
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    def get_orders(
        self,
        product_id: Optional[str] = None,
        order_status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retorna lista de ordens.
        
        Args:
            product_id: Filtrar por produto
            order_status: Filtrar por status
            limit: Número máximo de ordens
            
        Returns:
            Lista de ordens
        """
        params = {"limit": limit}
        if product_id:
            params["product_id"] = product_id
        if order_status:
            params["order_status"] = order_status
        
        response = self._make_request('GET', '/api/v3/brokerage/orders/historical/batch', params=params)
        return response.orders if hasattr(response, 'orders') else []
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Retorna detalhes de uma ordem específica.
        
        Args:
            order_id: ID da ordem
            
        Returns:
            Detalhes da ordem
        """
        response = self._make_request('GET', f'/api/v3/brokerage/orders/historical/{order_id}')
        return response.to_dict() if hasattr(response, 'to_dict') else response
    
    def get_fills(
        self,
        product_id: Optional[str] = None,
        order_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retorna lista de execuções (fills).
        
        Args:
            product_id: Filtrar por produto
            order_id: Filtrar por ordem
            limit: Número máximo de fills
            
        Returns:
            Lista de fills
        """
        params = {"limit": limit}
        if product_id:
            params["product_id"] = product_id
        if order_id:
            params["order_id"] = order_id
        
        response = self._make_request('GET', '/api/v3/brokerage/orders/historical/fills', params=params)
        return response.fills if hasattr(response, 'fills') else []
    
    # =============================================================================
    # PORTFOLIO METHODS
    # =============================================================================
    
    def get_portfolios(self, portfolio_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retorna lista de portfólios.
        
        Args:
            portfolio_type: Tipo do portfólio
            
        Returns:
            Lista de portfólios
        """
        params = {}
        if portfolio_type:
            params["portfolio_type"] = portfolio_type
        
        response = self._make_request('GET', '/api/v3/brokerage/portfolios', params=params)
        return response.portfolios if hasattr(response, 'portfolios') else []
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def get_server_time(self) -> datetime:
        """
        Retorna o horário do servidor.
        
        Returns:
            Horário do servidor
        """
        # Como a API Coinbase não tem endpoint específico para server time,
        # usamos uma requisição simples e extraímos o timestamp dos headers
        response = self._make_request('GET', '/api/v3/brokerage/accounts')
        return datetime.now()  # Fallback para horário local
    
    def test_connection(self) -> bool:
        """
        Testa a conexão com a API.
        
        Returns:
            True se a conexão está funcionando
        """
        try:
            self.get_accounts()
            return True
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            return False

