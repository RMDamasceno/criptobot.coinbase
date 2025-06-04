"""
Gerenciador de portfólio para trading.

Este módulo implementa o gerenciamento de portfólio, incluindo
tracking de posições, saldos, P&L e métricas de performance.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
import json

from ...config.settings import get_settings
from ...config.logging_config import get_logger
from ...core.exceptions import TradingException, InsufficientFundsException
from ..strategies.base_strategy import Position

logger = get_logger(__name__)


@dataclass
class AccountBalance:
    """Saldo da conta."""
    total_balance: float
    available_balance: float
    reserved_balance: float
    currency: str = "USD"
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class PortfolioMetrics:
    """Métricas do portfólio."""
    total_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    daily_pnl: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TradeHistory:
    """Histórico de trade."""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    entry_time: datetime
    exit_time: datetime
    strategy: str
    reason: str = "manual"


class PortfolioManager:
    """
    Gerenciador de portfólio.
    
    Responsável por:
    - Tracking de posições abertas
    - Cálculo de P&L realizado e não realizado
    - Métricas de performance
    - Gestão de saldos
    - Histórico de trades
    """
    
    def __init__(self, initial_balance: float = 10000.0, currency: str = "USD"):
        """
        Inicializa o gerenciador de portfólio.
        
        Args:
            initial_balance: Saldo inicial
            currency: Moeda base
        """
        self.settings = get_settings()
        
        # Saldo da conta
        self.account_balance = AccountBalance(
            total_balance=initial_balance,
            available_balance=initial_balance,
            reserved_balance=0.0,
            currency=currency
        )
        
        # Posições e trades
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeHistory] = []
        
        # Métricas de performance
        self.daily_pnl_history: List[Tuple[datetime, float]] = []
        self.balance_history: List[Tuple[datetime, float]] = []
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        
        # Estatísticas
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_realized_pnl = 0.0
        self.daily_pnl = 0.0
        
        # Tracking diário
        self.last_daily_reset = datetime.now().date()
        
        logger.info(
            "Portfolio manager initialized",
            initial_balance=initial_balance,
            currency=currency
        )
    
    def add_position(self, position: Position) -> bool:
        """
        Adiciona uma nova posição ao portfólio.
        
        Args:
            position: Posição a ser adicionada
            
        Returns:
            True se a posição foi adicionada com sucesso
            
        Raises:
            InsufficientFundsException: Se não há saldo suficiente
        """
        # Calcular valor necessário
        required_value = position.size * position.entry_price
        
        # Verificar saldo disponível
        if required_value > self.account_balance.available_balance:
            raise InsufficientFundsException(
                required_amount=required_value,
                available_amount=self.account_balance.available_balance
            )
        
        # Adicionar posição
        self.positions[position.symbol] = position
        
        # Atualizar saldos
        self.account_balance.available_balance -= required_value
        self.account_balance.reserved_balance += required_value
        self.account_balance.last_updated = datetime.now()
        
        logger.info(
            "Position added to portfolio",
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price,
            required_value=required_value,
            available_balance=self.account_balance.available_balance
        )
        
        return True
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "manual",
        strategy: str = "unknown"
    ) -> Optional[float]:
        """
        Fecha uma posição e calcula o P&L.
        
        Args:
            symbol: Símbolo da posição
            exit_price: Preço de saída
            reason: Motivo do fechamento
            strategy: Estratégia que fechou a posição
            
        Returns:
            P&L da posição ou None se não encontrada
        """
        if symbol not in self.positions:
            logger.warning(f"Position not found for closing: {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # Calcular P&L
        if position.side == "buy":
            pnl = (exit_price - position.entry_price) * position.size
        else:  # sell
            pnl = (position.entry_price - exit_price) * position.size
        
        # Calcular valor de fechamento
        close_value = position.size * exit_price
        
        # Atualizar saldos
        self.account_balance.available_balance += close_value
        self.account_balance.reserved_balance -= (position.size * position.entry_price)
        self.account_balance.total_balance += pnl
        self.account_balance.last_updated = datetime.now()
        
        # Atualizar estatísticas
        self.total_trades += 1
        self.total_realized_pnl += pnl
        self.daily_pnl += pnl
        
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Atualizar drawdown
        if self.account_balance.total_balance > self.peak_balance:
            self.peak_balance = self.account_balance.total_balance
        
        current_drawdown = (self.peak_balance - self.account_balance.total_balance) / self.peak_balance
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        # Adicionar ao histórico
        trade_record = TradeHistory(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            pnl=pnl,
            entry_time=position.timestamp or datetime.now(),
            exit_time=datetime.now(),
            strategy=strategy,
            reason=reason
        )
        self.trade_history.append(trade_record)
        
        # Remover posição
        del self.positions[symbol]
        
        logger.info(
            "Position closed",
            symbol=symbol,
            exit_price=exit_price,
            pnl=pnl,
            reason=reason,
            total_balance=self.account_balance.total_balance
        )
        
        return pnl
    
    def update_position_prices(self, prices: Dict[str, float]) -> None:
        """
        Atualiza os preços atuais das posições.
        
        Args:
            prices: Dicionário com preços atuais {symbol: price}
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                position = self.positions[symbol]
                position.current_price = price
                
                # Calcular P&L não realizado
                if position.side == "buy":
                    position.unrealized_pnl = (price - position.entry_price) * position.size
                else:  # sell
                    position.unrealized_pnl = (position.entry_price - price) * position.size
    
    def get_unrealized_pnl(self) -> float:
        """
        Calcula o P&L não realizado total.
        
        Returns:
            P&L não realizado
        """
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    def get_total_portfolio_value(self) -> float:
        """
        Calcula o valor total do portfólio.
        
        Returns:
            Valor total (saldo + P&L não realizado)
        """
        return self.account_balance.total_balance + self.get_unrealized_pnl()
    
    def get_position_value(self, symbol: str) -> Optional[float]:
        """
        Calcula o valor atual de uma posição.
        
        Args:
            symbol: Símbolo da posição
            
        Returns:
            Valor atual da posição ou None se não encontrada
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        return position.size * position.current_price
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """
        Calcula métricas detalhadas do portfólio.
        
        Returns:
            Métricas do portfólio
        """
        unrealized_pnl = self.get_unrealized_pnl()
        total_value = self.get_total_portfolio_value()
        
        # Calcular win rate
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        # Calcular médias
        avg_win = 0.0
        avg_loss = 0.0
        largest_win = 0.0
        largest_loss = 0.0
        
        if self.trade_history:
            winning_trades = [t.pnl for t in self.trade_history if t.pnl > 0]
            losing_trades = [t.pnl for t in self.trade_history if t.pnl < 0]
            
            if winning_trades:
                avg_win = sum(winning_trades) / len(winning_trades)
                largest_win = max(winning_trades)
            
            if losing_trades:
                avg_loss = sum(losing_trades) / len(losing_trades)
                largest_loss = min(losing_trades)
        
        # Calcular profit factor
        gross_profit = sum(t.pnl for t in self.trade_history if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trade_history if t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calcular Sharpe ratio (simplificado)
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        return PortfolioMetrics(
            total_value=total_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self.total_realized_pnl,
            total_pnl=self.total_realized_pnl + unrealized_pnl,
            daily_pnl=self.daily_pnl,
            win_rate=win_rate,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=self.max_drawdown * 100,  # Como percentual
            total_trades=self.total_trades,
            winning_trades=self.winning_trades,
            losing_trades=self.losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor
        )
    
    def _calculate_sharpe_ratio(self) -> float:
        """
        Calcula o Sharpe ratio baseado no histórico de P&L diário.
        
        Returns:
            Sharpe ratio
        """
        if len(self.daily_pnl_history) < 2:
            return 0.0
        
        # Calcular retornos diários
        daily_returns = [pnl for _, pnl in self.daily_pnl_history]
        
        # Calcular média e desvio padrão
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance ** 0.5
        
        # Sharpe ratio (assumindo risk-free rate = 0)
        return avg_return / std_dev if std_dev > 0 else 0.0
    
    def reset_daily_metrics(self) -> None:
        """Reseta métricas diárias (deve ser chamado no início de cada dia)."""
        # Salvar P&L do dia anterior
        if self.daily_pnl != 0:
            self.daily_pnl_history.append((datetime.now(), self.daily_pnl))
        
        # Salvar saldo histórico
        self.balance_history.append((datetime.now(), self.account_balance.total_balance))
        
        # Resetar P&L diário
        self.daily_pnl = 0.0
        self.last_daily_reset = datetime.now().date()
        
        logger.info("Daily metrics reset")
    
    def check_daily_reset(self) -> None:
        """Verifica se precisa resetar métricas diárias."""
        current_date = datetime.now().date()
        if current_date > self.last_daily_reset:
            self.reset_daily_metrics()
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo das posições abertas.
        
        Returns:
            Resumo das posições
        """
        positions_summary = {}
        
        for symbol, position in self.positions.items():
            positions_summary[symbol] = {
                "side": position.side,
                "size": position.size,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "unrealized_pnl_pct": (position.unrealized_pnl / (position.size * position.entry_price)) * 100,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "entry_time": position.timestamp.isoformat() if position.timestamp else None,
                "current_value": position.size * position.current_price
            }
        
        return positions_summary
    
    def get_trade_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retorna histórico de trades.
        
        Args:
            limit: Número máximo de trades a retornar
            
        Returns:
            Lista de trades
        """
        trades = self.trade_history[-limit:] if limit else self.trade_history
        
        return [
            {
                "symbol": trade.symbol,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "size": trade.size,
                "pnl": trade.pnl,
                "pnl_pct": (trade.pnl / (trade.size * trade.entry_price)) * 100,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "strategy": trade.strategy,
                "reason": trade.reason,
                "duration": str(trade.exit_time - trade.entry_time)
            }
            for trade in trades
        ]
    
    def export_data(self) -> Dict[str, Any]:
        """
        Exporta todos os dados do portfólio.
        
        Returns:
            Dados completos do portfólio
        """
        return {
            "account_balance": {
                "total_balance": self.account_balance.total_balance,
                "available_balance": self.account_balance.available_balance,
                "reserved_balance": self.account_balance.reserved_balance,
                "currency": self.account_balance.currency,
                "last_updated": self.account_balance.last_updated.isoformat()
            },
            "positions": self.get_position_summary(),
            "metrics": self.get_portfolio_metrics().__dict__,
            "trade_history": self.get_trade_history(),
            "daily_pnl_history": [
                {"date": date.isoformat(), "pnl": pnl}
                for date, pnl in self.daily_pnl_history
            ],
            "balance_history": [
                {"date": date.isoformat(), "balance": balance}
                for date, balance in self.balance_history
            ]
        }
    
    def save_to_file(self, filepath: str) -> None:
        """
        Salva dados do portfólio em arquivo.
        
        Args:
            filepath: Caminho do arquivo
        """
        try:
            data = self.export_data()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Portfolio data saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving portfolio data: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status atual do portfólio.
        
        Returns:
            Status do portfólio
        """
        metrics = self.get_portfolio_metrics()
        
        return {
            "account_balance": self.account_balance.total_balance,
            "available_balance": self.account_balance.available_balance,
            "total_portfolio_value": metrics.total_value,
            "unrealized_pnl": metrics.unrealized_pnl,
            "realized_pnl": metrics.realized_pnl,
            "daily_pnl": metrics.daily_pnl,
            "open_positions": len(self.positions),
            "total_trades": metrics.total_trades,
            "win_rate": metrics.win_rate,
            "max_drawdown": metrics.max_drawdown,
            "profit_factor": metrics.profit_factor,
            "last_updated": datetime.now().isoformat()
        }

