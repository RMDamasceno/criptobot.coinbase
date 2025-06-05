"""
Bot de Trading Principal.

Este módulo implementa o bot principal de trading que integra
sinais, estratégias, gestão de risco e execução de ordens.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..config.settings import get_settings
from ..config.logging_config import get_logger, log_trade_execution, log_performance_metrics
from ..core.coinbase_client import CoinbaseClient
from ..core.exceptions import CryptoBotsException, TradingException
from ..signals.signal_bot import SignalBot
from .strategies.base_strategy import TradingSignal, TradeOrder, Position
from .strategies.swing_strategy import SwingTradingStrategy
from .portfolio.portfolio_manager import PortfolioManager
from .risk_management.position_sizer import RiskManager

logger = get_logger(__name__)


@dataclass
class TradingBotConfig:
    """Configuração do bot de trading."""
    strategies: List[str]
    max_concurrent_trades: int
    update_interval: int
    dry_run: bool
    auto_start: bool


class TradingBot:
    """
    Bot principal de trading.
    
    Integra sinais de trading, estratégias, gestão de risco e execução
    de ordens para trading automatizado de criptomoedas.
    """
    
    def __init__(self, coinbase_client: Optional[CoinbaseClient] = None):
        """
        Inicializa o bot de trading.
        
        Args:
            coinbase_client: Cliente Coinbase (opcional)
        """
        self.settings = get_settings()
        self.coinbase_client = coinbase_client or CoinbaseClient()
        
        # Componentes principais
        self.signal_bot = SignalBot(self.coinbase_client)
        self.portfolio_manager = PortfolioManager(
            initial_balance=self.settings.initial_balance,
            currency="USD"
        )
        self.risk_manager = RiskManager()
        
        # Estratégias de trading
        self.strategies = {
            "swing_trading": SwingTradingStrategy()
        }
        
        # Configurações do bot
        self.trading_pairs = self.settings.trading_pairs
        self.update_interval = self.settings.trading_update_interval
        self.dry_run = self.settings.dry_run_mode
        self.max_concurrent_trades = self.settings.max_positions
        
        # Estado interno
        self.is_running = False
        self.last_signals: Dict[str, TradingSignal] = {}
        self.pending_orders: Dict[str, TradeOrder] = {}
        self.market_data_cache: Dict[str, Dict[str, Any]] = {}
        
        # Métricas de performance
        self.performance_metrics = {
            "trades_executed": 0,
            "orders_placed": 0,
            "errors": 0,
            "uptime_start": datetime.now(),
            "last_signal_time": None,
            "last_trade_time": None
        }
        
        logger.info(
            "Trading bot initialized",
            strategies=list(self.strategies.keys()),
            trading_pairs=self.trading_pairs,
            dry_run=self.dry_run,
            max_concurrent_trades=self.max_concurrent_trades
        )
    
    async def start(self) -> None:
        """Inicia o bot de trading."""
        if self.is_running:
            logger.warning("Trading bot is already running")
            return
        
        self.is_running = True
        self.performance_metrics["uptime_start"] = datetime.now()
        
        logger.info("Starting trading bot")
        
        # Verificar conexão com a API
        if not self.coinbase_client.test_connection():
            raise CryptoBotsException("Failed to connect to Coinbase API")
        
        # Inicializar estratégias
        for strategy in self.strategies.values():
            strategy.activate()
        
        try:
            # Loop principal
            while self.is_running:
                start_time = time.time()
                
                try:
                    await self._trading_cycle()
                    
                    # Métricas de performance
                    processing_time = time.time() - start_time
                    log_performance_metrics(
                        logger,
                        component="trading_bot",
                        operation="trading_cycle",
                        duration=processing_time,
                        success=True
                    )
                    
                except Exception as e:
                    self.performance_metrics["errors"] += 1
                    processing_time = time.time() - start_time
                    
                    log_performance_metrics(
                        logger,
                        component="trading_bot",
                        operation="trading_cycle",
                        duration=processing_time,
                        success=False,
                        error=str(e)
                    )
                    
                    logger.error("Error in trading cycle", error=str(e))
                
                # Aguardar próximo ciclo
                await asyncio.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("Trading bot stopped by user")
        except Exception as e:
            logger.error("Trading bot crashed", error=str(e))
            raise
        finally:
            self.is_running = False
            await self._cleanup()
    
    async def stop(self) -> None:
        """Para o bot de trading."""
        logger.info("Stopping trading bot")
        self.is_running = False
    
    async def _trading_cycle(self) -> None:
        """Executa um ciclo completo de trading."""
        # 1. Atualizar dados de mercado
        await self._update_market_data()
        
        # 2. Verificar reset diário
        self.portfolio_manager.check_daily_reset()
        
        # 3. Atualizar preços das posições
        await self._update_position_prices()
        
        # 4. Verificar posições para fechamento
        await self._check_position_exits()
        
        # 5. Obter novos sinais
        await self._process_new_signals()
        
        # 6. Executar ordens pendentes
        await self._execute_pending_orders()
        
        # 7. Salvar estado (periodicamente)
        await self._save_state()
    
    async def _update_market_data(self) -> None:
        """Atualiza dados de mercado para todos os pares."""
        for symbol in self.trading_pairs:
            try:
                # Obter ticker atual
                ticker = self.coinbase_client.get_market_trades(symbol)
                # ticker = self.coinbase_client.get_product_ticker(symbol)
                
                if ticker:
                    self.market_data_cache[symbol] = {
                        "price": float(ticker.get("price", 0)),
                        "volume": float(ticker.get("volume", 0)),
                        "timestamp": datetime.now(),
                        "account_balance": self.portfolio_manager.account_balance.total_balance
                    }
                
            except Exception as e:
                logger.error(f"Error updating market data for {symbol}", error=str(e))
    
    async def _update_position_prices(self) -> None:
        """Atualiza preços atuais das posições."""
        prices = {}
        
        for symbol in self.portfolio_manager.positions.keys():
            if symbol in self.market_data_cache:
                prices[symbol] = self.market_data_cache[symbol]["price"]
        
        if prices:
            self.portfolio_manager.update_position_prices(prices)
            
            # Atualizar também nas estratégias
            for strategy in self.strategies.values():
                for symbol, price in prices.items():
                    strategy.update_position_price(symbol, price)
    
    async def _check_position_exits(self) -> None:
        """Verifica se alguma posição deve ser fechada."""
        positions_to_close = []
        
        for symbol, position in self.portfolio_manager.positions.items():
            market_data = self.market_data_cache.get(symbol, {})
            
            # Verificar cada estratégia
            for strategy_name, strategy in self.strategies.items():
                if symbol in strategy.positions:
                    if strategy.should_close_position(position, market_data):
                        positions_to_close.append((symbol, strategy_name, "strategy_exit"))
                        break
        
        # Fechar posições identificadas
        for symbol, strategy_name, reason in positions_to_close:
            await self._close_position(symbol, reason, strategy_name)
    
    async def _process_new_signals(self) -> None:
        """Processa novos sinais de trading."""
        for symbol in self.trading_pairs:
            try:
                # Obter sinal do bot de sinais
                signal_result = await self.signal_bot.analyze_single_symbol(symbol)
                
                if signal_result and signal_result.get("analysis"):
                    # Converter para TradingSignal
                    trading_signal = self._convert_to_trading_signal(symbol, signal_result)
                    
                    if trading_signal:
                        self.last_signals[symbol] = trading_signal
                        self.performance_metrics["last_signal_time"] = datetime.now()
                        
                        # Processar sinal com estratégias
                        await self._process_signal_with_strategies(trading_signal)
                
            except Exception as e:
                logger.error(f"Error processing signals for {symbol}", error=str(e))
    
    def _convert_to_trading_signal(self, symbol: str, signal_result: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Converte resultado do bot de sinais para TradingSignal.
        
        Args:
            symbol: Símbolo do par
            signal_result: Resultado do bot de sinais
            
        Returns:
            TradingSignal ou None
        """
        try:
            analysis = signal_result["analysis"]
            
            # Mapear tipo de sinal
            signal_type_map = {
                "compra": "BUY",
                "venda": "SELL",
                "compra_forte": "STRONG_BUY",
                "venda_forte": "STRONG_SELL",
                "neutro": "HOLD"
            }
            
            signal_str = analysis.get("sinal", "neutro").lower()
            signal_type = signal_type_map.get(signal_str, "HOLD")
            
            # Obter preço atual
            current_price = self.market_data_cache.get(symbol, {}).get("price", 0)
            if not current_price:
                return None
            
            # Extrair métricas
            confidence_data = analysis.get("confianca", {})
            confidence = confidence_data.get("valor", 0) / 100 if confidence_data.get("valor") else 0
            
            trend_data = analysis.get("tendencia", {})
            strength_data = trend_data.get("forca", {}) if trend_data else {}
            strength = strength_data.get("valor", 0) / 100 if strength_data.get("valor") else 0
            
            return TradingSignal(
                symbol=symbol,
                signal_type=getattr(__import__("src.signals.indicators.technical_indicators", fromlist=["SignalType"]).SignalType, signal_type),
                strength=strength,
                confidence=confidence,
                entry_price=current_price,
                timestamp=datetime.now(),
                metadata=analysis
            )
            
        except Exception as e:
            logger.error(f"Error converting signal for {symbol}", error=str(e))
            return None
    
    async def _process_signal_with_strategies(self, signal: TradingSignal) -> None:
        """
        Processa um sinal com todas as estratégias ativas.
        
        Args:
            signal: Sinal de trading
        """
        market_data = self.market_data_cache.get(signal.symbol, {})
        
        for strategy_name, strategy in self.strategies.items():
            if not strategy.is_active:
                continue
            
            try:
                # Analisar sinal com a estratégia
                order = strategy.analyze_signal(signal, market_data)
                
                if order:
                    # Adicionar ordem às pendentes
                    order_id = f"{strategy_name}_{signal.symbol}_{datetime.now().timestamp()}"
                    order.client_order_id = order_id
                    self.pending_orders[order_id] = order
                    
                    logger.info(
                        "Order created from signal",
                        strategy=strategy_name,
                        symbol=signal.symbol,
                        side=order.side.value,
                        size=order.size,
                        order_type=order.order_type.value
                    )
                
            except Exception as e:
                logger.error(f"Error processing signal with strategy {strategy_name}", error=str(e))
    
    async def _execute_pending_orders(self) -> None:
        """Executa ordens pendentes."""
        orders_to_remove = []
        
        for order_id, order in self.pending_orders.items():
            try:
                success = await self._execute_order(order)
                
                if success:
                    orders_to_remove.append(order_id)
                    self.performance_metrics["orders_placed"] += 1
                
            except Exception as e:
                logger.error(f"Error executing order {order_id}", error=str(e))
                orders_to_remove.append(order_id)  # Remove ordem com erro
        
        # Remover ordens processadas
        for order_id in orders_to_remove:
            del self.pending_orders[order_id]
    
    async def _execute_order(self, order: TradeOrder) -> bool:
        """
        Executa uma ordem de trading.
        
        Args:
            order: Ordem a ser executada
            
        Returns:
            True se a ordem foi executada com sucesso
        """
        try:
            if self.dry_run:
                # Modo simulação
                return await self._simulate_order_execution(order)
            else:
                # Execução real
                return await self._execute_real_order(order)
                
        except Exception as e:
            logger.error(f"Error executing order for {order.symbol}", error=str(e))
            return False
    
    async def _simulate_order_execution(self, order: TradeOrder) -> bool:
        """
        Simula execução de ordem (modo dry run).
        
        Args:
            order: Ordem a ser simulada
            
        Returns:
            True se a simulação foi bem-sucedida
        """
        try:
            # Obter preço atual
            current_price = self.market_data_cache.get(order.symbol, {}).get("price")
            if not current_price:
                logger.warning(f"No current price for {order.symbol}")
                return False
            
            # Simular preenchimento da ordem
            fill_price = order.price if order.price else current_price
            
            # Criar posição
            position = Position(
                symbol=order.symbol,
                side=order.side.value,
                size=order.size,
                entry_price=fill_price,
                current_price=current_price,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                timestamp=datetime.now(),
                order_id=order.client_order_id
            )
            
            # Adicionar ao portfólio
            self.portfolio_manager.add_position(position)
            
            # Adicionar à estratégia
            strategy_name = order.metadata.get("strategy", "unknown")
            if strategy_name in self.strategies:
                self.strategies[strategy_name].add_position(position)
            
            # Log da execução
            log_trade_execution(
                logger,
                symbol=order.symbol,
                side=order.side.value,
                size=order.size,
                price=fill_price,
                order_type=order.order_type.value,
                strategy=strategy_name,
                dry_run=True
            )
            
            self.performance_metrics["trades_executed"] += 1
            self.performance_metrics["last_trade_time"] = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Error simulating order execution: {e}")
            return False
    
    async def _execute_real_order(self, order: TradeOrder) -> bool:
        """
        Executa ordem real na exchange.
        
        Args:
            order: Ordem a ser executada
            
        Returns:
            True se a ordem foi executada com sucesso
        """
        # Implementação da execução real seria aqui
        # Por enquanto, usar simulação
        logger.info("Real order execution not implemented, using simulation")
        return await self._simulate_order_execution(order)
    
    async def _close_position(self, symbol: str, reason: str, strategy_name: str) -> None:
        """
        Fecha uma posição.
        
        Args:
            symbol: Símbolo da posição
            reason: Motivo do fechamento
            strategy_name: Nome da estratégia
        """
        try:
            # Obter preço atual
            current_price = self.market_data_cache.get(symbol, {}).get("price")
            if not current_price:
                logger.warning(f"No current price for closing {symbol}")
                return
            
            # Fechar no portfólio
            pnl = self.portfolio_manager.close_position(symbol, current_price, reason, strategy_name)
            
            # Fechar na estratégia
            if strategy_name in self.strategies:
                self.strategies[strategy_name].remove_position(symbol, current_price, reason)
            
            if pnl is not None:
                logger.info(
                    "Position closed",
                    symbol=symbol,
                    exit_price=current_price,
                    pnl=pnl,
                    reason=reason,
                    strategy=strategy_name
                )
            
        except Exception as e:
            logger.error(f"Error closing position {symbol}", error=str(e))
    
    async def _save_state(self) -> None:
        """Salva estado do bot periodicamente."""
        try:
            # Salvar dados do portfólio
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"logs/portfolio_state_{timestamp}.json"
            self.portfolio_manager.save_to_file(filepath)
            
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    async def _cleanup(self) -> None:
        """Limpeza ao encerrar o bot."""
        logger.info("Cleaning up trading bot")
        
        # Desativar estratégias
        for strategy in self.strategies.values():
            strategy.deactivate()
        
        # Salvar estado final
        await self._save_state()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status atual do bot.
        
        Returns:
            Status do bot
        """
        uptime = datetime.now() - self.performance_metrics["uptime_start"]
        
        return {
            "is_running": self.is_running,
            "uptime": str(uptime).split('.')[0],
            "dry_run": self.dry_run,
            "trading_pairs": self.trading_pairs,
            "performance_metrics": self.performance_metrics.copy(),
            "portfolio_status": self.portfolio_manager.get_status(),
            "strategies": {
                name: strategy.get_status()
                for name, strategy in self.strategies.items()
            },
            "pending_orders": len(self.pending_orders),
            "market_data_age": {
                symbol: (datetime.now() - data.get("timestamp", datetime.now())).total_seconds()
                for symbol, data in self.market_data_cache.items()
            }
        }
    
    def add_strategy(self, name: str, strategy) -> None:
        """
        Adiciona uma nova estratégia.
        
        Args:
            name: Nome da estratégia
            strategy: Instância da estratégia
        """
        self.strategies[name] = strategy
        logger.info(f"Strategy '{name}' added to trading bot")
    
    def remove_strategy(self, name: str) -> None:
        """
        Remove uma estratégia.
        
        Args:
            name: Nome da estratégia
        """
        if name in self.strategies:
            self.strategies[name].deactivate()
            del self.strategies[name]
            logger.info(f"Strategy '{name}' removed from trading bot")
    
    async def force_close_all_positions(self) -> None:
        """Força o fechamento de todas as posições."""
        logger.info("Force closing all positions")
        
        positions = list(self.portfolio_manager.positions.keys())
        
        for symbol in positions:
            await self._close_position(symbol, "force_close", "manual")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo do portfólio.
        
        Returns:
            Resumo do portfólio
        """
        return {
            "portfolio_metrics": self.portfolio_manager.get_portfolio_metrics().__dict__,
            "positions": self.portfolio_manager.get_position_summary(),
            "recent_trades": self.portfolio_manager.get_trade_history(limit=10)
        }

