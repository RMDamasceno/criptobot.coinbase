"""
Sistema de gestão de risco para trading.

Este módulo implementa componentes para gestão de risco em trading,
incluindo cálculo de tamanho de posição, stop-loss e take-profit.
"""

from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from datetime import datetime

from ...config.settings import get_settings
from ...config.logging_config import get_logger
from ...core.exceptions import RiskManagementException, RiskLimitExceededException

logger = get_logger(__name__)


@dataclass
class PositionSize:
    """Resultado do cálculo de tamanho de posição."""
    base_size: float
    quote_size: float
    risk_amount: float
    risk_percentage: float
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass
class RiskLimits:
    """Limites de risco configurados."""
    max_risk_per_trade: float
    max_daily_loss: float
    max_positions: int
    min_position_size: float
    max_position_size: float


class PositionSizer:
    """
    Calculador de tamanho de posição baseado em gestão de risco.
    
    Calcula o tamanho ideal da posição baseado no risco definido,
    preço de entrada e stop-loss.
    """
    
    def __init__(self):
        """Inicializa o calculador de posição."""
        self.settings = get_settings()
        self.risk_limits = RiskLimits(
            max_risk_per_trade=self.settings.risk_percentage,
            max_daily_loss=self.settings.max_daily_loss,
            max_positions=self.settings.max_positions,
            min_position_size=self.settings.min_position_size,
            max_position_size=self.settings.max_position_size
        )
        
        logger.info(
            "Position sizer initialized",
            max_risk_per_trade=self.risk_limits.max_risk_per_trade,
            max_daily_loss=self.risk_limits.max_daily_loss,
            max_positions=self.risk_limits.max_positions
        )
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        side: str = "buy",
        risk_percentage: Optional[float] = None
    ) -> PositionSize:
        """
        Calcula o tamanho da posição baseado no risco.
        
        Args:
            account_balance: Saldo da conta
            entry_price: Preço de entrada
            stop_loss_price: Preço de stop-loss
            side: Lado da operação (buy/sell)
            risk_percentage: Percentual de risco (opcional)
            
        Returns:
            Tamanho da posição calculado
            
        Raises:
            RiskManagementException: Se os parâmetros são inválidos
        """
        if account_balance <= 0:
            raise RiskManagementException("Account balance must be positive")
        
        if entry_price <= 0 or stop_loss_price <= 0:
            raise RiskManagementException("Prices must be positive")
        
        # Usar risco configurado se não especificado
        risk_pct = risk_percentage or self.risk_limits.max_risk_per_trade
        
        # Calcular risco por unidade
        if side.lower() == "buy":
            if stop_loss_price >= entry_price:
                raise RiskManagementException("Stop-loss must be below entry price for buy orders")
            risk_per_unit = entry_price - stop_loss_price
        else:  # sell
            if stop_loss_price <= entry_price:
                raise RiskManagementException("Stop-loss must be above entry price for sell orders")
            risk_per_unit = stop_loss_price - entry_price
        
        # Calcular valor de risco total
        risk_amount = account_balance * (risk_pct / 100)
        
        # Calcular quantidade de unidades
        base_size = risk_amount / risk_per_unit
        
        # Aplicar limites mínimos e máximos
        base_size = max(base_size, self.risk_limits.min_position_size)
        base_size = min(base_size, self.risk_limits.max_position_size)
        
        # Calcular valor em quote currency
        quote_size = base_size * entry_price
        
        # Verificar se não excede o saldo
        if quote_size > account_balance:
            base_size = account_balance / entry_price
            quote_size = account_balance
            risk_amount = base_size * risk_per_unit
            risk_pct = (risk_amount / account_balance) * 100
        
        return PositionSize(
            base_size=base_size,
            quote_size=quote_size,
            risk_amount=risk_amount,
            risk_percentage=risk_pct,
            stop_loss_price=stop_loss_price
        )
    
    def calculate_kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calcula o tamanho da posição usando o critério de Kelly.
        
        Args:
            win_rate: Taxa de vitórias (0-1)
            avg_win: Ganho médio por trade vencedor
            avg_loss: Perda média por trade perdedor
            
        Returns:
            Percentual de capital a ser arriscado
        """
        if avg_loss <= 0:
            raise RiskManagementException("Average loss must be positive")
        
        # Fórmula de Kelly: f = (bp - q) / b
        # onde b = avg_win/avg_loss, p = win_rate, q = 1 - win_rate
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (b * p - q) / b
        
        # Limitar a no máximo 25% (Kelly conservador)
        kelly_fraction = max(0, min(kelly_fraction, 0.25))
        
        return kelly_fraction * 100  # Retornar como percentual


class StopLossManager:
    """
    Gerenciador de stop-loss para posições.
    
    Calcula e gerencia diferentes tipos de stop-loss,
    incluindo stop-loss fixo, trailing stop e stop baseado em ATR.
    """
    
    def __init__(self):
        """Inicializa o gerenciador de stop-loss."""
        self.settings = get_settings()
        self.default_stop_loss = self.settings.default_stop_loss
        
        logger.info("Stop-loss manager initialized", default_stop_loss=self.default_stop_loss)
    
    def calculate_fixed_stop_loss(
        self,
        entry_price: float,
        side: str,
        stop_loss_percentage: Optional[float] = None
    ) -> float:
        """
        Calcula stop-loss fixo baseado em percentual.
        
        Args:
            entry_price: Preço de entrada
            side: Lado da operação (buy/sell)
            stop_loss_percentage: Percentual de stop-loss
            
        Returns:
            Preço de stop-loss
        """
        stop_pct = stop_loss_percentage or self.default_stop_loss
        
        if side.lower() == "buy":
            stop_price = entry_price * (1 - stop_pct / 100)
        else:  # sell
            stop_price = entry_price * (1 + stop_pct / 100)
        
        return stop_price
    
    def calculate_atr_stop_loss(
        self,
        entry_price: float,
        atr_value: float,
        side: str,
        atr_multiplier: float = 2.0
    ) -> float:
        """
        Calcula stop-loss baseado em ATR (Average True Range).
        
        Args:
            entry_price: Preço de entrada
            atr_value: Valor do ATR
            side: Lado da operação
            atr_multiplier: Multiplicador do ATR
            
        Returns:
            Preço de stop-loss
        """
        atr_distance = atr_value * atr_multiplier
        
        if side.lower() == "buy":
            stop_price = entry_price - atr_distance
        else:  # sell
            stop_price = entry_price + atr_distance
        
        return stop_price
    
    def update_trailing_stop(
        self,
        current_price: float,
        entry_price: float,
        current_stop: float,
        side: str,
        trailing_percentage: float = 2.0
    ) -> float:
        """
        Atualiza stop-loss trailing.
        
        Args:
            current_price: Preço atual
            entry_price: Preço de entrada
            current_stop: Stop-loss atual
            side: Lado da operação
            trailing_percentage: Percentual de trailing
            
        Returns:
            Novo preço de stop-loss
        """
        if side.lower() == "buy":
            # Para posições compradas, o stop sobe quando o preço sobe
            new_stop = current_price * (1 - trailing_percentage / 100)
            return max(current_stop, new_stop)
        else:  # sell
            # Para posições vendidas, o stop desce quando o preço desce
            new_stop = current_price * (1 + trailing_percentage / 100)
            return min(current_stop, new_stop)


class TakeProfitManager:
    """
    Gerenciador de take-profit para posições.
    
    Calcula e gerencia diferentes estratégias de take-profit,
    incluindo take-profit fixo, escalonado e baseado em suporte/resistência.
    """
    
    def __init__(self):
        """Inicializa o gerenciador de take-profit."""
        self.settings = get_settings()
        self.default_take_profit = self.settings.default_take_profit
        
        logger.info("Take-profit manager initialized", default_take_profit=self.default_take_profit)
    
    def calculate_fixed_take_profit(
        self,
        entry_price: float,
        side: str,
        take_profit_percentage: Optional[float] = None
    ) -> float:
        """
        Calcula take-profit fixo baseado em percentual.
        
        Args:
            entry_price: Preço de entrada
            side: Lado da operação
            take_profit_percentage: Percentual de take-profit
            
        Returns:
            Preço de take-profit
        """
        tp_pct = take_profit_percentage or self.default_take_profit
        
        if side.lower() == "buy":
            tp_price = entry_price * (1 + tp_pct / 100)
        else:  # sell
            tp_price = entry_price * (1 - tp_pct / 100)
        
        return tp_price
    
    def calculate_risk_reward_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
        risk_reward_ratio: float = 2.0
    ) -> float:
        """
        Calcula take-profit baseado na relação risco/recompensa.
        
        Args:
            entry_price: Preço de entrada
            stop_loss_price: Preço de stop-loss
            side: Lado da operação
            risk_reward_ratio: Relação risco/recompensa
            
        Returns:
            Preço de take-profit
        """
        if side.lower() == "buy":
            risk = entry_price - stop_loss_price
            tp_price = entry_price + (risk * risk_reward_ratio)
        else:  # sell
            risk = stop_loss_price - entry_price
            tp_price = entry_price - (risk * risk_reward_ratio)
        
        return tp_price
    
    def calculate_scaled_take_profits(
        self,
        entry_price: float,
        side: str,
        levels: int = 3,
        max_percentage: float = 6.0
    ) -> list[Tuple[float, float]]:
        """
        Calcula múltiplos níveis de take-profit escalonados.
        
        Args:
            entry_price: Preço de entrada
            side: Lado da operação
            levels: Número de níveis
            max_percentage: Percentual máximo
            
        Returns:
            Lista de tuplas (preço, percentual_da_posição)
        """
        take_profits = []
        
        for i in range(1, levels + 1):
            # Percentual crescente para cada nível
            percentage = (max_percentage / levels) * i
            
            if side.lower() == "buy":
                price = entry_price * (1 + percentage / 100)
            else:  # sell
                price = entry_price * (1 - percentage / 100)
            
            # Percentual da posição a ser fechado (distribuição igual)
            position_percentage = 1.0 / levels
            
            take_profits.append((price, position_percentage))
        
        return take_profits


class RiskManager:
    """
    Gerenciador principal de risco.
    
    Coordena todos os aspectos de gestão de risco,
    incluindo validação de trades e monitoramento de exposição.
    """
    
    def __init__(self):
        """Inicializa o gerenciador de risco."""
        self.settings = get_settings()
        self.position_sizer = PositionSizer()
        self.stop_loss_manager = StopLossManager()
        self.take_profit_manager = TakeProfitManager()
        
        # Tracking de risco
        self.daily_pnl = 0.0
        self.open_positions = 0
        self.total_exposure = 0.0
        
        logger.info("Risk manager initialized")
    
    def validate_trade(
        self,
        account_balance: float,
        entry_price: float,
        position_size: float,
        side: str
    ) -> Tuple[bool, str]:
        """
        Valida se um trade pode ser executado baseado nas regras de risco.
        
        Args:
            account_balance: Saldo da conta
            entry_price: Preço de entrada
            position_size: Tamanho da posição
            side: Lado da operação
            
        Returns:
            Tupla (pode_executar, motivo)
        """
        # Verificar número máximo de posições
        if self.open_positions >= self.position_sizer.risk_limits.max_positions:
            return False, f"Maximum positions exceeded ({self.open_positions}/{self.position_sizer.risk_limits.max_positions})"
        
        # Verificar tamanho mínimo e máximo
        if position_size < self.position_sizer.risk_limits.min_position_size:
            return False, f"Position size below minimum ({position_size} < {self.position_sizer.risk_limits.min_position_size})"
        
        if position_size > self.position_sizer.risk_limits.max_position_size:
            return False, f"Position size above maximum ({position_size} > {self.position_sizer.risk_limits.max_position_size})"
        
        # Verificar saldo suficiente
        required_balance = position_size * entry_price
        if required_balance > account_balance:
            return False, f"Insufficient balance ({required_balance} > {account_balance})"
        
        # Verificar perda diária máxima
        if self.daily_pnl < -self.position_sizer.risk_limits.max_daily_loss:
            return False, f"Daily loss limit exceeded ({abs(self.daily_pnl)}% > {self.position_sizer.risk_limits.max_daily_loss}%)"
        
        return True, "Trade validated"
    
    def update_position_count(self, change: int) -> None:
        """
        Atualiza o contador de posições abertas.
        
        Args:
            change: Mudança no número de posições (+1 para abrir, -1 para fechar)
        """
        self.open_positions = max(0, self.open_positions + change)
        logger.debug("Position count updated", open_positions=self.open_positions, change=change)
    
    def update_daily_pnl(self, pnl: float) -> None:
        """
        Atualiza o P&L diário.
        
        Args:
            pnl: Lucro/prejuízo do trade
        """
        self.daily_pnl += pnl
        logger.debug("Daily PnL updated", daily_pnl=self.daily_pnl, trade_pnl=pnl)
    
    def reset_daily_metrics(self) -> None:
        """Reseta métricas diárias (deve ser chamado no início de cada dia)."""
        self.daily_pnl = 0.0
        logger.info("Daily metrics reset")
    
    def get_risk_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual de risco.
        
        Returns:
            Status de risco
        """
        return {
            "open_positions": self.open_positions,
            "max_positions": self.position_sizer.risk_limits.max_positions,
            "daily_pnl": self.daily_pnl,
            "max_daily_loss": self.position_sizer.risk_limits.max_daily_loss,
            "total_exposure": self.total_exposure,
            "risk_limits": {
                "max_risk_per_trade": self.position_sizer.risk_limits.max_risk_per_trade,
                "min_position_size": self.position_sizer.risk_limits.min_position_size,
                "max_position_size": self.position_sizer.risk_limits.max_position_size
            }
        }

