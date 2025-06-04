"""
Testes unitários para estratégias de trading.

Este módulo contém testes para validar o funcionamento correto
das estratégias de trading implementadas.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

from src.trading.strategies.base_strategy import BaseStrategy, TradingSignal, TradeOrder, Position, OrderType, OrderSide
from src.trading.strategies.swing_strategy import SwingTradingStrategy
from src.signals.indicators.technical_indicators import SignalType


class MockStrategy(BaseStrategy):
    """Estratégia mock para testes da classe base."""
    
    def __init__(self):
        super().__init__("Mock Strategy")
        self.analyze_signal_calls = []
        self.should_close_calls = []
    
    def analyze_signal(self, signal, market_data):
        self.analyze_signal_calls.append((signal, market_data))
        # Retornar ordem mock para sinais de compra/venda
        if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
            return TradeOrder(
                symbol=signal.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                size=0.1,
                price=signal.entry_price
            )
        return None
    
    def should_close_position(self, position, market_data):
        self.should_close_calls.append((position, market_data))
        return False


class TestBaseStrategy(unittest.TestCase):
    """Testes para a estratégia base."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        self.strategy = MockStrategy()
        
        # Sinal de teste
        self.test_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.BUY,
            strength=0.8,
            confidence=0.75,
            entry_price=50000.0,
            timestamp=datetime.now()
        )
        
        # Posição de teste
        self.test_position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=51000.0,
            timestamp=datetime.now()
        )
    
    def test_strategy_initialization(self):
        """Testa inicialização da estratégia."""
        self.assertEqual(self.strategy.name, "Mock Strategy")
        self.assertTrue(self.strategy.is_active)
        self.assertEqual(len(self.strategy.positions), 0)
        self.assertEqual(self.strategy.total_trades, 0)
        self.assertEqual(self.strategy.total_pnl, 0.0)
    
    def test_validate_signal(self):
        """Testa validação de sinais."""
        # Sinal válido
        self.assertTrue(self.strategy.validate_signal(self.test_signal))
        
        # Sinal com força baixa
        weak_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.BUY,
            strength=0.3,  # Abaixo do threshold
            confidence=0.75,
            entry_price=50000.0
        )
        self.assertFalse(self.strategy.validate_signal(weak_signal))
        
        # Sinal com confiança baixa
        low_confidence_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.BUY,
            strength=0.8,
            confidence=0.4,  # Abaixo do threshold
            entry_price=50000.0
        )
        self.assertFalse(self.strategy.validate_signal(low_confidence_signal))
    
    @patch('src.trading.strategies.base_strategy.RiskManager')
    def test_calculate_position_size(self, mock_risk_manager):
        """Testa cálculo de tamanho de posição."""
        # Mock do position sizer
        mock_position_size = Mock()
        mock_position_size.base_size = 0.1
        mock_position_size.quote_size = 5000.0
        mock_position_size.risk_amount = 100.0
        mock_position_size.stop_loss_price = 48000.0
        
        mock_risk_manager.return_value.position_sizer.calculate_position_size.return_value = mock_position_size
        mock_risk_manager.return_value.stop_loss_manager.calculate_fixed_stop_loss.return_value = 48000.0
        
        # Criar nova estratégia para usar o mock
        strategy = MockStrategy()
        
        result = strategy.calculate_position_size(self.test_signal, 10000.0)
        
        self.assertEqual(result.base_size, 0.1)
        self.assertEqual(result.quote_size, 5000.0)
        self.assertEqual(result.risk_amount, 100.0)
    
    def test_add_position(self):
        """Testa adição de posição."""
        self.strategy.add_position(self.test_position)
        
        self.assertEqual(len(self.strategy.positions), 1)
        self.assertIn("BTC-USD", self.strategy.positions)
        self.assertEqual(self.strategy.positions["BTC-USD"], self.test_position)
    
    def test_remove_position(self):
        """Testa remoção de posição."""
        # Adicionar posição primeiro
        self.strategy.add_position(self.test_position)
        
        # Remover posição
        pnl = self.strategy.remove_position("BTC-USD", 52000.0, "test")
        
        self.assertEqual(len(self.strategy.positions), 0)
        self.assertNotIn("BTC-USD", self.strategy.positions)
        self.assertEqual(pnl, 200.0)  # (52000 - 50000) * 0.1
        self.assertEqual(self.strategy.total_trades, 1)
        self.assertEqual(self.strategy.winning_trades, 1)
        self.assertEqual(self.strategy.total_pnl, 200.0)
    
    def test_update_position_price(self):
        """Testa atualização de preço da posição."""
        self.strategy.add_position(self.test_position)
        
        self.strategy.update_position_price("BTC-USD", 52000.0)
        
        position = self.strategy.positions["BTC-USD"]
        self.assertEqual(position.current_price, 52000.0)
        self.assertEqual(position.unrealized_pnl, 200.0)  # (52000 - 50000) * 0.1
    
    def test_performance_metrics(self):
        """Testa cálculo de métricas de performance."""
        # Adicionar algumas posições e trades
        self.strategy.add_position(self.test_position)
        self.strategy.remove_position("BTC-USD", 52000.0, "profit")  # Trade vencedor
        
        # Adicionar trade perdedor
        losing_position = Position(
            symbol="ETH-USD",
            side="buy",
            size=1.0,
            entry_price=3000.0,
            current_price=2800.0,
            timestamp=datetime.now()
        )
        self.strategy.add_position(losing_position)
        self.strategy.remove_position("ETH-USD", 2800.0, "loss")  # Trade perdedor
        
        metrics = self.strategy.get_performance_metrics()
        
        self.assertEqual(metrics["total_trades"], 2)
        self.assertEqual(metrics["winning_trades"], 1)
        self.assertEqual(metrics["losing_trades"], 1)
        self.assertEqual(metrics["win_rate"], 50.0)
        self.assertEqual(metrics["total_pnl"], 0.0)  # 200 - 200 = 0
    
    def test_strategy_activation(self):
        """Testa ativação/desativação da estratégia."""
        self.assertTrue(self.strategy.is_active)
        
        self.strategy.deactivate()
        self.assertFalse(self.strategy.is_active)
        
        self.strategy.activate()
        self.assertTrue(self.strategy.is_active)


class TestSwingTradingStrategy(unittest.TestCase):
    """Testes para a estratégia de swing trading."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        self.strategy = SwingTradingStrategy()
        
        # Sinal forte para swing trading
        self.strong_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.STRONG_BUY,
            strength=0.85,
            confidence=0.8,
            entry_price=50000.0,
            timestamp=datetime.now()
        )
        
        # Dados de mercado mock
        self.market_data = {
            "price": 50000.0,
            "volume": 2000000,  # Volume alto
            "volatility": 0.02,
            "trend": "bullish",
            "account_balance": 10000.0
        }
    
    def test_swing_strategy_initialization(self):
        """Testa inicialização da estratégia de swing trading."""
        self.assertEqual(self.strategy.name, "Swing Trading")
        self.assertEqual(self.strategy.min_signal_strength, 0.7)
        self.assertEqual(self.strategy.min_confidence, 0.65)
        self.assertEqual(self.strategy.stop_loss_percentage, 3.0)
        self.assertEqual(self.strategy.take_profit_ratio, 2.5)
    
    def test_validate_swing_signal(self):
        """Testa validação específica do swing trading."""
        # Sinal válido
        self.assertTrue(self.strategy._validate_swing_signal(self.strong_signal, self.market_data))
        
        # Sinal com força baixa
        weak_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.BUY,
            strength=0.6,  # Abaixo do threshold do swing
            confidence=0.8,
            entry_price=50000.0
        )
        self.assertFalse(self.strategy._validate_swing_signal(weak_signal, self.market_data))
        
        # Volume baixo
        low_volume_data = self.market_data.copy()
        low_volume_data["volume"] = 500000  # Abaixo do threshold
        self.assertFalse(self.strategy._validate_swing_signal(self.strong_signal, low_volume_data))
    
    def test_should_enter_position(self):
        """Testa decisão de entrada em posição."""
        # Sinal forte - deve entrar
        self.assertTrue(self.strategy._should_enter_position(self.strong_signal, self.market_data))
        
        # Sinal médio com confiança alta - deve entrar
        medium_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.BUY,
            strength=0.75,
            confidence=0.8,  # Confiança alta
            entry_price=50000.0
        )
        self.assertTrue(self.strategy._should_enter_position(medium_signal, self.market_data))
        
        # Sinal médio com confiança baixa - não deve entrar
        medium_signal.confidence = 0.6
        self.assertFalse(self.strategy._should_enter_position(medium_signal, self.market_data))
        
        # Sinal HOLD - não deve entrar
        hold_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.HOLD,
            strength=0.8,
            confidence=0.8,
            entry_price=50000.0
        )
        self.assertFalse(self.strategy._should_enter_position(hold_signal, self.market_data))
    
    def test_calculate_swing_stop_loss(self):
        """Testa cálculo de stop-loss para swing trading."""
        # Para compra
        stop_loss = self.strategy._calculate_swing_stop_loss(self.strong_signal)
        expected_stop = 50000.0 * (1 - 3.0 / 100)  # 3% abaixo
        self.assertAlmostEqual(stop_loss, expected_stop, places=2)
        
        # Para venda
        sell_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.STRONG_SELL,
            strength=0.85,
            confidence=0.8,
            entry_price=50000.0
        )
        stop_loss = self.strategy._calculate_swing_stop_loss(sell_signal)
        expected_stop = 50000.0 * (1 + 3.0 / 100)  # 3% acima
        self.assertAlmostEqual(stop_loss, expected_stop, places=2)
    
    def test_calculate_swing_take_profit(self):
        """Testa cálculo de take-profit para swing trading."""
        stop_loss = 48500.0  # 3% abaixo de 50000
        take_profit = self.strategy._calculate_swing_take_profit(self.strong_signal, stop_loss)
        
        # Take profit deve ser 2.5x o risco
        risk = 50000.0 - 48500.0  # 1500
        expected_tp = 50000.0 + (risk * 2.5)  # 53750
        self.assertAlmostEqual(take_profit, expected_tp, places=2)
    
    @patch('src.trading.strategies.swing_strategy.SwingTradingStrategy.calculate_position_size')
    @patch('src.trading.strategies.swing_strategy.SwingTradingStrategy.validate_signal')
    def test_analyze_signal(self, mock_validate, mock_calc_size):
        """Testa análise de sinal completa."""
        # Configurar mocks
        mock_validate.return_value = True
        
        mock_position_size = Mock()
        mock_position_size.base_size = 0.1
        mock_position_size.stop_loss_price = 48500.0
        mock_calc_size.return_value = mock_position_size
        
        # Mock do risk manager
        with patch.object(self.strategy.risk_manager, 'validate_trade') as mock_risk_validate:
            mock_risk_validate.return_value = (True, "Trade validated")
            
            order = self.strategy.analyze_signal(self.strong_signal, self.market_data)
            
            self.assertIsNotNone(order)
            self.assertEqual(order.symbol, "BTC-USD")
            self.assertEqual(order.side, OrderSide.BUY)
            self.assertEqual(order.order_type, OrderType.LIMIT)
            self.assertEqual(order.size, 0.1)
    
    def test_position_exit_conditions(self):
        """Testa condições de saída de posição."""
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=52000.0,
            stop_loss=48500.0,
            take_profit=53750.0,
            timestamp=datetime.now()
        )
        
        # Preço atual normal - não deve fechar
        self.assertFalse(self.strategy.should_close_position(position, self.market_data))
        
        # Stop-loss atingido
        position.current_price = 48000.0
        self.assertTrue(self.strategy.should_close_position(position, self.market_data))
        
        # Take-profit atingido
        position.current_price = 54000.0
        self.assertTrue(self.strategy.should_close_position(position, self.market_data))
        
        # Tempo máximo atingido
        position.current_price = 51000.0  # Preço normal
        position.timestamp = datetime.now() - timedelta(days=15)  # Mais de 14 dias
        self.assertTrue(self.strategy.should_close_position(position, self.market_data))
    
    def test_estimate_hold_period(self):
        """Testa estimativa de período de manutenção."""
        # Sinal muito forte
        strong_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.STRONG_BUY,
            strength=0.95,
            confidence=0.9,
            entry_price=50000.0
        )
        days = self.strategy._estimate_hold_period(strong_signal)
        self.assertEqual(days, 7)
        
        # Sinal médio
        medium_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.BUY,
            strength=0.75,
            confidence=0.7,
            entry_price=50000.0
        )
        days = self.strategy._estimate_hold_period(medium_signal)
        self.assertEqual(days, 3)
    
    def test_assess_market_conditions(self):
        """Testa avaliação de condições de mercado."""
        # Alta volatilidade
        high_vol_data = self.market_data.copy()
        high_vol_data["volatility"] = 0.06
        condition = self.strategy._assess_market_conditions(high_vol_data)
        self.assertEqual(condition, "high_volatility")
        
        # Baixa volatilidade
        low_vol_data = self.market_data.copy()
        low_vol_data["volatility"] = 0.005
        condition = self.strategy._assess_market_conditions(low_vol_data)
        self.assertEqual(condition, "low_volatility")
        
        # Alto volume
        high_vol_data = self.market_data.copy()
        high_vol_data["volume"] = 3000000
        condition = self.strategy._assess_market_conditions(high_vol_data)
        self.assertEqual(condition, "high_volume")
        
        # Condições normais
        condition = self.strategy._assess_market_conditions(self.market_data)
        self.assertEqual(condition, "normal")


class TestStrategyIntegration(unittest.TestCase):
    """Testes de integração para estratégias."""
    
    def setUp(self):
        """Configuração inicial."""
        self.strategy = SwingTradingStrategy()
    
    def test_complete_trading_cycle(self):
        """Testa ciclo completo de trading."""
        # 1. Sinal de entrada
        entry_signal = TradingSignal(
            symbol="BTC-USD",
            signal_type=SignalType.STRONG_BUY,
            strength=0.85,
            confidence=0.8,
            entry_price=50000.0,
            timestamp=datetime.now()
        )
        
        market_data = {
            "price": 50000.0,
            "volume": 2000000,
            "volatility": 0.02,
            "trend": "bullish",
            "account_balance": 10000.0
        }
        
        # 2. Analisar sinal (mock dos componentes necessários)
        with patch.object(self.strategy, 'validate_signal', return_value=True), \
             patch.object(self.strategy, 'calculate_position_size') as mock_calc_size, \
             patch.object(self.strategy.risk_manager, 'validate_trade', return_value=(True, "OK")):
            
            mock_position_size = Mock()
            mock_position_size.base_size = 0.1
            mock_position_size.stop_loss_price = 48500.0
            mock_calc_size.return_value = mock_position_size
            
            order = self.strategy.analyze_signal(entry_signal, market_data)
            
            self.assertIsNotNone(order)
            self.assertEqual(order.symbol, "BTC-USD")
            self.assertEqual(order.side, OrderSide.BUY)
        
        # 3. Simular execução da ordem
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=50000.0,
            stop_loss=48500.0,
            take_profit=53750.0,
            timestamp=datetime.now()
        )
        
        self.strategy.add_position(position)
        
        # 4. Atualizar preços e verificar saída
        # Preço sobe - não deve fechar
        self.strategy.update_position_price("BTC-USD", 52000.0)
        self.assertFalse(self.strategy.should_close_position(position, market_data))
        
        # Take-profit atingido - deve fechar
        self.strategy.update_position_price("BTC-USD", 54000.0)
        self.assertTrue(self.strategy.should_close_position(position, market_data))
        
        # 5. Fechar posição
        pnl = self.strategy.remove_position("BTC-USD", 54000.0, "take_profit")
        
        self.assertEqual(pnl, 400.0)  # (54000 - 50000) * 0.1
        self.assertEqual(self.strategy.total_trades, 1)
        self.assertEqual(self.strategy.winning_trades, 1)


if __name__ == '__main__':
    # Configurar logging para testes
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Executar testes
    unittest.main(verbosity=2)

