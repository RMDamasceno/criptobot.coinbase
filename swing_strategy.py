"""
Estratégia de Swing Trading.

Esta estratégia implementa swing trading baseado em sinais de análise técnica,
mantendo posições por períodos médios (dias a semanas) para capturar
movimentos de tendência.
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from ...config.logging_config import get_logger
from ...signals.indicators.technical_indicators import SignalType
from .base_strategy import BaseStrategy, TradingSignal, TradeOrder, Position, OrderType, OrderSide

logger = get_logger(__name__)


class SwingTradingStrategy(BaseStrategy):
    """
    Estratégia de Swing Trading.
    
    Características:
    - Mantém posições por dias a semanas
    - Foca em tendências de médio prazo
    - Usa stop-loss e take-profit mais amplos
    - Menor frequência de trades
    """
    
    def __init__(self):
        """Inicializa a estratégia de swing trading."""
        super().__init__("Swing Trading")
        
        # Configurações específicas da estratégia
        self.min_signal_strength = 0.7  # Força mínima do sinal
        self.min_confidence = 0.65      # Confiança mínima
        self.stop_loss_percentage = 3.0  # Stop-loss mais amplo
        self.take_profit_ratio = 2.5     # Relação risco/recompensa
        self.max_hold_days = 14          # Máximo de dias para manter posição
        
        # Filtros de mercado
        self.min_volume_threshold = 1000000  # Volume mínimo
        self.avoid_news_hours = True         # Evitar horários de notícias
        
        logger.info(
            "Swing trading strategy initialized",
            min_signal_strength=self.min_signal_strength,
            min_confidence=self.min_confidence,
            stop_loss_percentage=self.stop_loss_percentage,
            take_profit_ratio=self.take_profit_ratio
        )
    
    def analyze_signal(self, signal: TradingSignal, market_data: Dict[str, Any]) -> Optional[TradeOrder]:
        """
        Analisa um sinal para swing trading.
        
        Args:
            signal: Sinal de trading
            market_data: Dados de mercado atuais
            
        Returns:
            Ordem de trade ou None
        """
        if not self.is_active:
            return None
        
        # Validações básicas
        if not self.validate_signal(signal):
            return None
        
        # Validações específicas do swing trading
        if not self._validate_swing_signal(signal, market_data):
            return None
        
        # Verificar se deve operar baseado no tipo de sinal
        if not self._should_enter_position(signal, market_data):
            return None
        
        try:
            # Obter saldo da conta (simulado para teste)
            account_balance = market_data.get('account_balance', 10000.0)
            
            # Calcular tamanho da posição
            position_size = self.calculate_position_size(signal, account_balance)
            
            # Validar trade com gestão de risco
            can_trade, reason = self.risk_manager.validate_trade(
                account_balance=account_balance,
                entry_price=signal.entry_price,
                position_size=position_size.base_size,
                side="buy" if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell"
            )
            
            if not can_trade:
                logger.info(f"Trade rejected by risk manager: {reason}")
                return None
            
            # Ajustar stop-loss e take-profit para swing trading
            stop_loss = self._calculate_swing_stop_loss(signal)
            take_profit = self._calculate_swing_take_profit(signal, stop_loss)
            
            # Atualizar sinal com novos valores
            signal.stop_loss = stop_loss
            signal.take_profit = take_profit
            
            # Criar ordem
            order = self.create_order_from_signal(
                signal=signal,
                position_size=position_size,
                order_type=OrderType.LIMIT  # Usar limit orders para swing trading
            )
            
            # Adicionar metadados específicos
            order.metadata.update({
                "strategy_type": "swing_trading",
                "expected_hold_days": self._estimate_hold_period(signal),
                "market_conditions": self._assess_market_conditions(market_data)
            })
            
            logger.info(
                "Swing trading order created",
                symbol=signal.symbol,
                side=order.side.value,
                size=order.size,
                entry_price=signal.entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error creating swing trading order: {e}")
            return None
    
    def should_close_position(self, position: Position, market_data: Dict[str, Any]) -> bool:
        """
        Decide se uma posição de swing trading deve ser fechada.
        
        Args:
            position: Posição atual
            market_data: Dados de mercado atuais
            
        Returns:
            True se deve fechar a posição
        """
        current_price = position.current_price
        
        # Verificar stop-loss
        if self._check_stop_loss(position, current_price):
            logger.info(f"Stop-loss triggered for {position.symbol}")
            return True
        
        # Verificar take-profit
        if self._check_take_profit(position, current_price):
            logger.info(f"Take-profit triggered for {position.symbol}")
            return True
        
        # Verificar tempo máximo de manutenção
        if self._check_max_hold_time(position):
            logger.info(f"Max hold time reached for {position.symbol}")
            return True
        
        # Verificar reversão de tendência
        if self._check_trend_reversal(position, market_data):
            logger.info(f"Trend reversal detected for {position.symbol}")
            return True
        
        # Verificar trailing stop
        if self._check_trailing_stop(position, current_price):
            logger.info(f"Trailing stop triggered for {position.symbol}")
            return True
        
        return False
    
    def _validate_swing_signal(self, signal: TradingSignal, market_data: Dict[str, Any]) -> bool:
        """
        Validações específicas para swing trading.
        
        Args:
            signal: Sinal de trading
            market_data: Dados de mercado
            
        Returns:
            True se o sinal é válido para swing trading
        """
        # Verificar força mínima do sinal
        if signal.strength < self.min_signal_strength:
            logger.debug(f"Signal strength too low for swing trading: {signal.strength}")
            return False
        
        # Verificar confiança mínima
        if signal.confidence < self.min_confidence:
            logger.debug(f"Signal confidence too low for swing trading: {signal.confidence}")
            return False
        
        # Verificar volume
        volume = market_data.get('volume', 0)
        if volume < self.min_volume_threshold:
            logger.debug(f"Volume too low for swing trading: {volume}")
            return False
        
        # Evitar sinais muito fracos (apenas HOLD)
        if signal.signal_type == SignalType.HOLD:
            return False
        
        return True
    
    def _should_enter_position(self, signal: TradingSignal, market_data: Dict[str, Any]) -> bool:
        """
        Decide se deve entrar em uma posição baseado no sinal.
        
        Args:
            signal: Sinal de trading
            market_data: Dados de mercado
            
        Returns:
            True se deve entrar na posição
        """
        # Para swing trading, preferir sinais fortes
        strong_signals = [SignalType.STRONG_BUY, SignalType.STRONG_SELL]
        medium_signals = [SignalType.BUY, SignalType.SELL]
        
        if signal.signal_type in strong_signals:
            return True
        elif signal.signal_type in medium_signals:
            # Para sinais médios, exigir confiança maior
            return signal.confidence >= 0.75
        
        return False
    
    def _calculate_swing_stop_loss(self, signal: TradingSignal) -> float:
        """
        Calcula stop-loss específico para swing trading.
        
        Args:
            signal: Sinal de trading
            
        Returns:
            Preço de stop-loss
        """
        side = "buy" if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell"
        
        return self.risk_manager.stop_loss_manager.calculate_fixed_stop_loss(
            entry_price=signal.entry_price,
            side=side,
            stop_loss_percentage=self.stop_loss_percentage
        )
    
    def _calculate_swing_take_profit(self, signal: TradingSignal, stop_loss: float) -> float:
        """
        Calcula take-profit específico para swing trading.
        
        Args:
            signal: Sinal de trading
            stop_loss: Preço de stop-loss
            
        Returns:
            Preço de take-profit
        """
        side = "buy" if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell"
        
        return self.risk_manager.take_profit_manager.calculate_risk_reward_take_profit(
            entry_price=signal.entry_price,
            stop_loss_price=stop_loss,
            side=side,
            risk_reward_ratio=self.take_profit_ratio
        )
    
    def _estimate_hold_period(self, signal: TradingSignal) -> int:
        """
        Estima o período de manutenção da posição.
        
        Args:
            signal: Sinal de trading
            
        Returns:
            Número estimado de dias
        """
        # Baseado na força do sinal
        if signal.strength >= 0.9:
            return 7  # Sinais muito fortes: ~1 semana
        elif signal.strength >= 0.8:
            return 5  # Sinais fortes: ~5 dias
        else:
            return 3  # Sinais médios: ~3 dias
    
    def _assess_market_conditions(self, market_data: Dict[str, Any]) -> str:
        """
        Avalia as condições de mercado.
        
        Args:
            market_data: Dados de mercado
            
        Returns:
            Descrição das condições
        """
        volatility = market_data.get('volatility', 0.02)
        volume = market_data.get('volume', 0)
        
        if volatility > 0.05:
            return "high_volatility"
        elif volatility < 0.01:
            return "low_volatility"
        elif volume > self.min_volume_threshold * 2:
            return "high_volume"
        else:
            return "normal"
    
    def _check_stop_loss(self, position: Position, current_price: float) -> bool:
        """Verifica se o stop-loss foi atingido."""
        if not position.stop_loss:
            return False
        
        if position.side == "buy":
            return current_price <= position.stop_loss
        else:  # sell
            return current_price >= position.stop_loss
    
    def _check_take_profit(self, position: Position, current_price: float) -> bool:
        """Verifica se o take-profit foi atingido."""
        if not position.take_profit:
            return False
        
        if position.side == "buy":
            return current_price >= position.take_profit
        else:  # sell
            return current_price <= position.take_profit
    
    def _check_max_hold_time(self, position: Position) -> bool:
        """Verifica se o tempo máximo de manutenção foi atingido."""
        if not position.timestamp:
            return False
        
        hold_time = datetime.now() - position.timestamp
        return hold_time.days >= self.max_hold_days
    
    def _check_trend_reversal(self, position: Position, market_data: Dict[str, Any]) -> bool:
        """
        Verifica se houve reversão de tendência.
        
        Args:
            position: Posição atual
            market_data: Dados de mercado
            
        Returns:
            True se houve reversão
        """
        # Implementação simplificada - em produção usaria indicadores técnicos
        trend = market_data.get('trend', 'sideways')
        
        if position.side == "buy" and trend == "bearish":
            return True
        elif position.side == "sell" and trend == "bullish":
            return True
        
        return False
    
    def _check_trailing_stop(self, position: Position, current_price: float) -> bool:
        """
        Verifica trailing stop para swing trading.
        
        Args:
            position: Posição atual
            current_price: Preço atual
            
        Returns:
            True se trailing stop foi atingido
        """
        # Implementação simplificada de trailing stop
        trailing_percentage = 2.0  # 2% trailing stop
        
        if position.side == "buy":
            # Para posições compradas, verificar se o preço caiu muito do pico
            if hasattr(position, 'peak_price'):
                trailing_stop = position.peak_price * (1 - trailing_percentage / 100)
                return current_price <= trailing_stop
        else:  # sell
            # Para posições vendidas, verificar se o preço subiu muito do vale
            if hasattr(position, 'valley_price'):
                trailing_stop = position.valley_price * (1 + trailing_percentage / 100)
                return current_price >= trailing_stop
        
        return False
    
    def update_position_price(self, symbol: str, current_price: float) -> None:
        """
        Atualiza preço da posição e trailing stops.
        
        Args:
            symbol: Símbolo da posição
            current_price: Preço atual
        """
        super().update_position_price(symbol, current_price)
        
        if symbol in self.positions:
            position = self.positions[symbol]
            
            # Atualizar picos e vales para trailing stop
            if position.side == "buy":
                if not hasattr(position, 'peak_price') or current_price > position.peak_price:
                    position.peak_price = current_price
            else:  # sell
                if not hasattr(position, 'valley_price') or current_price < position.valley_price:
                    position.valley_price = current_price

