"""
Testes unitários para indicadores técnicos.

Este módulo contém testes para validar o funcionamento correto
dos indicadores técnicos implementados.
"""

import unittest
import numpy as np
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

from src.signals.indicators.technical_indicators import TechnicalIndicators, SignalType, IndicatorResult


class TestTechnicalIndicators(unittest.TestCase):
    """Testes para indicadores técnicos."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        # Dados de teste - preços simulados
        self.prices_bullish = [100 + i * 0.5 for i in range(50)]  # Tendência de alta
        self.prices_bearish = [100 - i * 0.5 for i in range(50)]  # Tendência de baixa
        self.prices_sideways = [100 + np.sin(i * 0.1) * 2 for i in range(50)]  # Lateral
        
        # Dados insuficientes
        self.prices_short = [100, 101, 102]
        
        # Dados com volatilidade alta
        self.prices_volatile = []
        for i in range(50):
            base = 100
            volatility = np.random.normal(0, 5)  # 5% de volatilidade
            self.prices_volatile.append(base + volatility)
    
    def test_rsi_calculation(self):
        """Testa cálculo do RSI."""
        # Teste com tendência de alta
        result = TechnicalIndicators.rsi(self.prices_bullish)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertGreater(result.value, 50)  # RSI deve ser > 50 em tendência de alta
        self.assertLessEqual(result.value, 100)
        self.assertGreaterEqual(result.value, 0)
        
        # Teste com tendência de baixa
        result = TechnicalIndicators.rsi(self.prices_bearish)
        self.assertLess(result.value, 50)  # RSI deve ser < 50 em tendência de baixa
        
        # Teste com dados insuficientes
        with self.assertRaises(Exception):  # Pode ser ValueError ou InsufficientDataException
            TechnicalIndicators.rsi(self.prices_short)
    
    def test_rsi_signals(self):
        """Testa sinais do RSI."""
        # Criar dados para RSI sobrecomprado (>70)
        prices_overbought = [100 + i * 2 for i in range(30)]
        result = TechnicalIndicators.rsi(prices_overbought)
        
        if result.value > 70:
            self.assertEqual(result.signal, SignalType.SELL)
        
        # Criar dados para RSI sobrevendido (<30)
        prices_oversold = [100 - i * 2 for i in range(30)]
        result = TechnicalIndicators.rsi(prices_oversold)
        
        if result.value < 30:
            self.assertEqual(result.signal, SignalType.BUY)
    
    def test_macd_calculation(self):
        """Testa cálculo do MACD."""
        result = TechnicalIndicators.macd(self.prices_bullish)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertIn('macd', result.value)
        self.assertIn('signal', result.value)
        self.assertIn('histogram', result.value)
        
        # Verificar tipos
        self.assertIsInstance(result.value['macd'], float)
        self.assertIsInstance(result.value['signal'], float)
        self.assertIsInstance(result.value['histogram'], float)
    
    def test_macd_signals(self):
        """Testa sinais do MACD."""
        result = TechnicalIndicators.macd(self.prices_bullish)
        
        # Em tendência de alta, MACD deve tender a ser positivo
        if result.value['histogram'] > 0:
            self.assertIn(result.signal, [SignalType.BUY, SignalType.STRONG_BUY, SignalType.HOLD])
    
    def test_bollinger_bands_calculation(self):
        """Testa cálculo das Bollinger Bands."""
        result = TechnicalIndicators.bollinger_bands(self.prices_sideways)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertIn('upper', result.value)
        self.assertIn('middle', result.value)
        self.assertIn('lower', result.value)
        self.assertIn('position', result.value)
        
        # Banda superior deve ser maior que a média
        self.assertGreater(result.value['upper'], result.value['middle'])
        # Banda inferior deve ser menor que a média
        self.assertLess(result.value['lower'], result.value['middle'])
        
        # Posição deve estar entre 0 e 1
        self.assertGreaterEqual(result.value['position'], 0)
        self.assertLessEqual(result.value['position'], 1)
    
    def test_bollinger_bands_signals(self):
        """Testa sinais das Bollinger Bands."""
        result = TechnicalIndicators.bollinger_bands(self.prices_sideways)
        
        # Verificar lógica dos sinais baseada na posição
        if result.value['position'] > 0.8:
            self.assertEqual(result.signal, SignalType.SELL)
        elif result.value['position'] < 0.2:
            self.assertEqual(result.signal, SignalType.BUY)
        else:
            self.assertEqual(result.signal, SignalType.HOLD)
    
    def test_moving_averages_calculation(self):
        """Testa cálculo das médias móveis."""
        result = TechnicalIndicators.moving_averages(self.prices_bullish)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertIn('short_ma', result.value)
        self.assertIn('long_ma', result.value)
        self.assertIn('divergence', result.value)
        
        # Em tendência de alta, MA curta deve ser maior que MA longa
        self.assertGreater(result.value['short_ma'], result.value['long_ma'])
        
        # Divergência deve ser positiva em tendência de alta
        self.assertGreater(result.value['divergence'], 0)
    
    def test_moving_averages_signals(self):
        """Testa sinais das médias móveis."""
        # Tendência de alta
        result = TechnicalIndicators.moving_averages(self.prices_bullish)
        if result.value['divergence'] > 2:  # Divergência > 2%
            self.assertIn(result.signal, [SignalType.BUY, SignalType.STRONG_BUY])
        
        # Tendência de baixa
        result = TechnicalIndicators.moving_averages(self.prices_bearish)
        if result.value['divergence'] < -2:  # Divergência < -2%
            self.assertIn(result.signal, [SignalType.SELL, SignalType.STRONG_SELL])
    
    def test_stochastic_calculation(self):
        """Testa cálculo do Estocástico."""
        # Criar dados de OHLC
        ohlc_data = {
            'high': [p + 2 for p in self.prices_bullish],
            'low': [p - 2 for p in self.prices_bullish],
            'close': self.prices_bullish
        }
        
        result = TechnicalIndicators.stochastic(ohlc_data)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertIn('%K', result.value)
        self.assertIn('%D', result.value)
        
        # Valores devem estar entre 0 e 100
        self.assertGreaterEqual(result.value['%K'], 0)
        self.assertLessEqual(result.value['%K'], 100)
        self.assertGreaterEqual(result.value['%D'], 0)
        self.assertLessEqual(result.value['%D'], 100)
    
    def test_williams_r_calculation(self):
        """Testa cálculo do Williams %R."""
        # Criar dados de OHLC
        ohlc_data = {
            'high': [p + 2 for p in self.prices_bullish],
            'low': [p - 2 for p in self.prices_bullish],
            'close': self.prices_bullish
        }
        
        result = TechnicalIndicators.williams_r(ohlc_data)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertIsInstance(result.value, float)
        
        # Valor deve estar entre -100 e 0
        self.assertGreaterEqual(result.value, -100)
        self.assertLessEqual(result.value, 0)
    
    def test_combine_signals(self):
        """Testa combinação de sinais."""
        # Criar indicadores de teste
        indicators = [
            IndicatorResult(SignalType.BUY, 0.8, 65.0),
            IndicatorResult(SignalType.STRONG_BUY, 0.9, 75.0),
            IndicatorResult(SignalType.HOLD, 0.5, 50.0),
            IndicatorResult(SignalType.BUY, 0.7, 60.0)
        ]
        
        weights = [1.0, 1.5, 1.0, 1.2]
        
        result = TechnicalIndicators.combine_signals(indicators, weights)
        
        self.assertIsInstance(result, IndicatorResult)
        self.assertIn('buy_score', result.value)
        self.assertIn('sell_score', result.value)
        self.assertIn('hold_score', result.value)
        
        # Scores devem somar aproximadamente 1.0
        total_score = (result.value['buy_score'] + 
                      result.value['sell_score'] + 
                      result.value['hold_score'])
        self.assertAlmostEqual(total_score, 1.0, places=2)
        
        # Com maioria de sinais de compra, deve resultar em BUY
        self.assertIn(result.signal, [SignalType.BUY, SignalType.STRONG_BUY])
    
    def test_edge_cases(self):
        """Testa casos extremos."""
        # Lista vazia
        with self.assertRaises(Exception):
            TechnicalIndicators.rsi([])
        
        # Valores None
        with self.assertRaises(Exception):
            TechnicalIndicators.rsi([None, 100, 101])
        
        # Valores negativos
        negative_prices = [-100, -99, -98]
        with self.assertRaises(Exception):
            TechnicalIndicators.rsi(negative_prices)
        
        # Preços iguais (sem variação)
        flat_prices = [100] * 50
        result = TechnicalIndicators.rsi(flat_prices)
        # RSI deve ser próximo de 50 quando não há variação
        self.assertAlmostEqual(result.value, 50, delta=5)
    
    def test_signal_strength_calculation(self):
        """Testa cálculo da força do sinal."""
        # RSI extremo deve ter força alta
        extreme_prices = [100 + i * 3 for i in range(30)]  # Movimento forte
        result = TechnicalIndicators.rsi(extreme_prices)
        
        if result.value > 80 or result.value < 20:
            self.assertGreater(result.strength, 0.7)
        
        # RSI neutro deve ter força baixa
        neutral_prices = [100 + np.sin(i * 0.1) * 0.5 for i in range(50)]
        result = TechnicalIndicators.rsi(neutral_prices)
        
        if 40 <= result.value <= 60:
            self.assertLess(result.strength, 0.6)
    
    def test_performance(self):
        """Testa performance dos indicadores."""
        import time
        
        # Dados grandes para teste de performance
        large_dataset = [100 + np.sin(i * 0.01) * 10 + np.random.normal(0, 1) 
                        for i in range(1000)]
        
        # Teste RSI
        start_time = time.time()
        result = TechnicalIndicators.rsi(large_dataset)
        rsi_time = time.time() - start_time
        
        self.assertLess(rsi_time, 1.0)  # Deve executar em menos de 1 segundo
        self.assertIsInstance(result, IndicatorResult)
        
        # Teste MACD
        start_time = time.time()
        result = TechnicalIndicators.macd(large_dataset)
        macd_time = time.time() - start_time
        
        self.assertLess(macd_time, 1.0)
        self.assertIsInstance(result, IndicatorResult)


class TestIndicatorIntegration(unittest.TestCase):
    """Testes de integração para indicadores."""
    
    def test_real_market_scenario(self):
        """Testa cenário de mercado real simulado."""
        # Simular dados de mercado com diferentes fases
        market_data = []
        
        # Fase 1: Acumulação (lateral)
        for i in range(50):
            price = 100 + np.sin(i * 0.2) * 2 + np.random.normal(0, 0.5)
            market_data.append(price)
        
        # Fase 2: Tendência de alta
        for i in range(30):
            price = market_data[-1] + np.random.normal(1, 0.8)
            market_data.append(price)
        
        # Fase 3: Correção
        for i in range(20):
            price = market_data[-1] + np.random.normal(-0.5, 0.6)
            market_data.append(price)
        
        # Testar todos os indicadores
        rsi = TechnicalIndicators.rsi(market_data)
        macd = TechnicalIndicators.macd(market_data)
        bb = TechnicalIndicators.bollinger_bands(market_data)
        ma = TechnicalIndicators.moving_averages(market_data)
        
        # Todos devem retornar resultados válidos
        for indicator in [rsi, macd, bb, ma]:
            self.assertIsInstance(indicator, IndicatorResult)
            self.assertIsInstance(indicator.signal, SignalType)
            self.assertGreaterEqual(indicator.strength, 0)
            self.assertLessEqual(indicator.strength, 1)
        
        # Combinar sinais
        combined = TechnicalIndicators.combine_signals(
            [rsi, macd, bb, ma],
            [1.0, 1.5, 1.0, 2.0]
        )
        
        self.assertIsInstance(combined, IndicatorResult)
        self.assertIsInstance(combined.signal, SignalType)


if __name__ == '__main__':
    # Configurar logging para testes
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Executar testes
    unittest.main(verbosity=2)

