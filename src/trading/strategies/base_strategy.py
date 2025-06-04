"""
Estratégia base para trading.

Este módulo define a interface base para todas as estratégias de trading
e implementa funcionalidades comuns.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ...config.settings import get_settings
from ...config.logging_config import get_logger
from ...core.exceptions import TradingException, InvalidOrderException
from ...signals.indicators.technical_indicators import SignalType
from ..risk_management.position_sizer import RiskManager, PositionSize

logger = get_logger(__name__)


class OrderType(Enum):
    """Tipos de ordem."""
    MARKET = "market_order"
    LIMIT = "limit_order"
    STOP = "stop_order"
    STOP_LIMIT = "stop_limit_order"


class OrderSide(Enum):
    """Lado da ordem."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class TradingSignal:
    """Sinal de trading processado."""
    symbol: str
    signal_type: SignalType
    strength: float
    confidence: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = None
    metadata: Dict[str, Any] = None


@dataclass
class TradeOrder:
    """Ordem de trade a ser executada."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class Position:
    """Posição aberta."""
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    timestamp: datetime = None
    order_id: Optional[str] = None


class BaseStrategy(ABC):
    """
    Classe base para estratégias de trading.
    
    Define a interface comum que todas as estratégias devem implementar
    e fornece funcionalidades básicas de gestão de risco.
    """
    
    def __init__(self, name: str):
        """
        Inicializa a estratégia base.
        
        Args:
            name: Nome da estratégia
        """
        self.name = name
        self.settings = get_settings()
        self.risk_manager = RiskManager()
        
        # Estado da estratégia
        self.is_active = True
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, TradeOrder] = {}
        
        # Métricas de performance
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = 0.0
        
        logger.info(f"Strategy '{name}' initialized")
    
    @abstractmethod
    def analyze_signal(self, signal: TradingSignal, market_data: Dict[str, Any]) -> Optional[TradeOrder]:
        """
        Analisa um sinal e decide se deve gerar uma ordem.
        
        Args:
            signal: Sinal de trading
            market_data: Dados de mercado atuais
            
        Returns:
            Ordem de trade ou None se não deve operar
        """
        pass
    
    @abstractmethod
    def should_close_position(self, position: Position, market_data: Dict[str, Any]) -> bool:
        """
        Decide se uma posição deve ser fechada.
        
        Args:
            position: Posição atual
            market_data: Dados de mercado atuais
            
        Returns:
            True se deve fechar a posição
        """
        pass
    
    def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Valida se um sinal atende aos critérios da estratégia.
        
        Args:
            signal: Sinal de trading
            
        Returns:
            True se o sinal é válido
        """
        # Verificar força mínima do sinal
        if signal.strength < self.settings.signal_strength_threshold:
            logger.debug(
                f"Signal strength below threshold for {signal.symbol}",
                strength=signal.strength,
                threshold=self.settings.signal_strength_threshold
            )
            return False
        
        # Verificar confiança mínima
        min_confidence = 0.6  # 60% de confiança mínima
        if signal.confidence < min_confidence:
            logger.debug(
                f"Signal confidence below threshold for {signal.symbol}",
                confidence=signal.confidence,
                threshold=min_confidence
            )
            return False
        
        # Verificar se já existe posição para o símbolo
        if signal.symbol in self.positions:
            logger.debug(f"Position already exists for {signal.symbol}")
            return False
        
        return True
    
    def calculate_position_size(
        self,
        signal: TradingSignal,
        account_balance: float
    ) -> PositionSize:
        """
        Calcula o tamanho da posição baseado no sinal e gestão de risco.
        
        Args:
            signal: Sinal de trading
            account_balance: Saldo da conta
            
        Returns:
            Tamanho da posição calculado
        """
        # Determinar preços
        entry_price = signal.entry_price
        stop_loss_price = signal.stop_loss
        
        # Se não há stop-loss no sinal, calcular um
        if not stop_loss_price:
            side = "buy" if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell"
            stop_loss_price = self.risk_manager.stop_loss_manager.calculate_fixed_stop_loss(
                entry_price, side
            )
        
        # Calcular tamanho da posição
        side = "buy" if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell"
        position_size = self.risk_manager.position_sizer.calculate_position_size(
            account_balance=account_balance,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            side=side
        )
        
        return position_size
    
    def create_order_from_signal(
        self,
        signal: TradingSignal,
        position_size: PositionSize,
        order_type: OrderType = OrderType.MARKET
    ) -> TradeOrder:
        """
        Cria uma ordem de trade baseada no sinal.
        
        Args:
            signal: Sinal de trading
            position_size: Tamanho da posição
            order_type: Tipo da ordem
            
        Returns:
            Ordem de trade
        """
        # Determinar lado da ordem
        if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
            side = OrderSide.BUY
        elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            side = OrderSide.SELL
        else:
            raise InvalidOrderException(f"Invalid signal type for order: {signal.signal_type}")
        
        # Calcular take-profit se não fornecido
        take_profit = signal.take_profit
        if not take_profit and position_size.stop_loss_price:
            take_profit = self.risk_manager.take_profit_manager.calculate_risk_reward_take_profit(
                entry_price=signal.entry_price,
                stop_loss_price=position_size.stop_loss_price,
                side=side.value
            )
        
        return TradeOrder(
            symbol=signal.symbol,
            side=side,
            order_type=order_type,
            size=position_size.base_size,
            price=signal.entry_price if order_type == OrderType.LIMIT else None,
            stop_loss=position_size.stop_loss_price,
            take_profit=take_profit,
            metadata={
                "strategy": self.name,
                "signal_strength": signal.strength,
                "signal_confidence": signal.confidence,
                "risk_amount": position_size.risk_amount,
                "risk_percentage": position_size.risk_percentage
            }
        )
    
    def add_position(self, position: Position) -> None:
        """
        Adiciona uma nova posição.
        
        Args:
            position: Posição a ser adicionada
        """
        self.positions[position.symbol] = position
        self.risk_manager.update_position_count(1)
        
        logger.info(
            "Position added",
            strategy=self.name,
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price
        )
    
    def remove_position(self, symbol: str, exit_price: float, reason: str = "manual") -> Optional[float]:
        """
        Remove uma posição e calcula o P&L.
        
        Args:
            symbol: Símbolo da posição
            exit_price: Preço de saída
            reason: Motivo do fechamento
            
        Returns:
            P&L da posição ou None se não encontrada
        """
        if symbol not in self.positions:
            logger.warning(f"Position not found for removal: {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # Calcular P&L
        if position.side == "buy":
            pnl = (exit_price - position.entry_price) * position.size
        else:  # sell
            pnl = (position.entry_price - exit_price) * position.size
        
        # Atualizar métricas
        self.total_trades += 1
        self.total_pnl += pnl
        
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Atualizar drawdown
        if self.total_pnl > self.peak_balance:
            self.peak_balance = self.total_pnl
        
        current_drawdown = (self.peak_balance - self.total_pnl) / self.peak_balance if self.peak_balance > 0 else 0
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        # Remover posição
        del self.positions[symbol]
        self.risk_manager.update_position_count(-1)
        self.risk_manager.update_daily_pnl(pnl)
        
        logger.info(
            "Position closed",
            strategy=self.name,
            symbol=symbol,
            exit_price=exit_price,
            pnl=pnl,
            reason=reason
        )
        
        return pnl
    
    def update_position_price(self, symbol: str, current_price: float) -> None:
        """
        Atualiza o preço atual de uma posição.
        
        Args:
            symbol: Símbolo da posição
            current_price: Preço atual
        """
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = current_price
            
            # Calcular P&L não realizado
            if position.side == "buy":
                position.unrealized_pnl = (current_price - position.entry_price) * position.size
            else:  # sell
                position.unrealized_pnl = (position.entry_price - current_price) * position.size
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Retorna métricas de performance da estratégia.
        
        Returns:
            Métricas de performance
        """
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_win = self.total_pnl / self.winning_trades if self.winning_trades > 0 else 0
        avg_loss = abs(self.total_pnl) / self.losing_trades if self.losing_trades > 0 else 0
        
        return {
            "strategy_name": self.name,
            "is_active": self.is_active,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "total_pnl": self.total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown": self.max_drawdown * 100,  # Como percentual
            "open_positions": len(self.positions),
            "risk_status": self.risk_manager.get_risk_status()
        }
    
    def reset_metrics(self) -> None:
        """Reseta as métricas de performance."""
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = 0.0
        
        logger.info(f"Metrics reset for strategy '{self.name}'")
    
    def activate(self) -> None:
        """Ativa a estratégia."""
        self.is_active = True
        logger.info(f"Strategy '{self.name}' activated")
    
    def deactivate(self) -> None:
        """Desativa a estratégia."""
        self.is_active = False
        logger.info(f"Strategy '{self.name}' deactivated")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual da estratégia.
        
        Returns:
            Status da estratégia
        """
        return {
            "name": self.name,
            "is_active": self.is_active,
            "open_positions": len(self.positions),
            "pending_orders": len(self.pending_orders),
            "performance": self.get_performance_metrics(),
            "positions": {
                symbol: {
                    "side": pos.side,
                    "size": pos.size,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit
                }
                for symbol, pos in self.positions.items()
            }
        }

