#!/usr/bin/env python3
"""
Teste dos indicadores técnicos.

Script para testar os indicadores técnicos com dados simulados.
"""

import sys
from pathlib import Path
import numpy as np

# Adicionar diretório raiz ao path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from src.signals.indicators.technical_indicators import TechnicalIndicators, SignalType


def generate_test_data(length=100, trend="sideways"):
    """Gera dados de teste para os indicadores."""
    np.random.seed(42)  # Para resultados reproduzíveis
    
    base_price = 50000  # Preço base (ex: Bitcoin)
    prices = [base_price]
    
    for i in range(1, length):
        # Movimento aleatório
        random_change = np.random.normal(0, 0.02)  # 2% de volatilidade
        
        # Adicionar tendência
        if trend == "bullish":
            trend_change = 0.001  # 0.1% de tendência de alta
        elif trend == "bearish":
            trend_change = -0.001  # 0.1% de tendência de baixa
        else:
            trend_change = 0
        
        # Calcular novo preço
        change = random_change + trend_change
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
    
    return prices


def test_rsi():
    """Testa o indicador RSI."""
    print("=== Testando RSI ===")
    
    # Teste com tendência de alta
    bullish_prices = generate_test_data(50, "bullish")
    rsi_result = TechnicalIndicators.rsi(bullish_prices)
    
    print(f"Tendência de alta:")
    print(f"  RSI: {rsi_result.value:.2f}")
    print(f"  Sinal: {rsi_result.signal.value}")
    print(f"  Força: {rsi_result.strength:.2f}")
    
    # Teste com tendência de baixa
    bearish_prices = generate_test_data(50, "bearish")
    rsi_result = TechnicalIndicators.rsi(bearish_prices)
    
    print(f"Tendência de baixa:")
    print(f"  RSI: {rsi_result.value:.2f}")
    print(f"  Sinal: {rsi_result.signal.value}")
    print(f"  Força: {rsi_result.strength:.2f}")
    
    print()


def test_macd():
    """Testa o indicador MACD."""
    print("=== Testando MACD ===")
    
    # Teste com tendência de alta
    bullish_prices = generate_test_data(100, "bullish")
    macd_result = TechnicalIndicators.macd(bullish_prices)
    
    print(f"Tendência de alta:")
    print(f"  MACD: {macd_result.value['macd']:.4f}")
    print(f"  Signal: {macd_result.value['signal']:.4f}")
    print(f"  Histogram: {macd_result.value['histogram']:.4f}")
    print(f"  Sinal: {macd_result.signal.value}")
    print(f"  Força: {macd_result.strength:.2f}")
    
    print()


def test_bollinger_bands():
    """Testa as Bollinger Bands."""
    print("=== Testando Bollinger Bands ===")
    
    # Teste com dados laterais
    sideways_prices = generate_test_data(50, "sideways")
    bb_result = TechnicalIndicators.bollinger_bands(sideways_prices)
    
    print(f"Movimento lateral:")
    print(f"  Banda Superior: {bb_result.value['upper']:.2f}")
    print(f"  Banda Média: {bb_result.value['middle']:.2f}")
    print(f"  Banda Inferior: {bb_result.value['lower']:.2f}")
    print(f"  Posição: {bb_result.value['position']:.2f}")
    print(f"  Sinal: {bb_result.signal.value}")
    print(f"  Força: {bb_result.strength:.2f}")
    
    print()


def test_moving_averages():
    """Testa as médias móveis."""
    print("=== Testando Médias Móveis ===")
    
    # Teste com tendência de alta
    bullish_prices = generate_test_data(100, "bullish")
    ma_result = TechnicalIndicators.moving_averages(bullish_prices)
    
    print(f"Tendência de alta:")
    print(f"  MA Curta: {ma_result.value['short_ma']:.2f}")
    print(f"  MA Longa: {ma_result.value['long_ma']:.2f}")
    print(f"  Divergência: {ma_result.value['divergence']:.2f}%")
    print(f"  Sinal: {ma_result.signal.value}")
    print(f"  Força: {ma_result.strength:.2f}")
    
    print()


def test_combined_signals():
    """Testa a combinação de sinais."""
    print("=== Testando Combinação de Sinais ===")
    
    # Gerar dados de teste
    prices = generate_test_data(100, "bullish")
    
    # Calcular indicadores
    rsi = TechnicalIndicators.rsi(prices)
    macd = TechnicalIndicators.macd(prices)
    bb = TechnicalIndicators.bollinger_bands(prices)
    ma = TechnicalIndicators.moving_averages(prices)
    
    # Combinar sinais
    indicators = [rsi, macd, bb, ma]
    weights = [1.0, 1.5, 1.0, 2.0]
    
    combined = TechnicalIndicators.combine_signals(indicators, weights)
    
    print(f"Sinais individuais:")
    print(f"  RSI: {rsi.signal.value} (força: {rsi.strength:.2f})")
    print(f"  MACD: {macd.signal.value} (força: {macd.strength:.2f})")
    print(f"  Bollinger: {bb.signal.value} (força: {bb.strength:.2f})")
    print(f"  MA: {ma.signal.value} (força: {ma.strength:.2f})")
    
    print(f"\nSinal combinado:")
    print(f"  Sinal: {combined.signal.value}")
    print(f"  Força: {combined.strength:.2f}")
    print(f"  Score Compra: {combined.value['buy_score']:.2f}")
    print(f"  Score Venda: {combined.value['sell_score']:.2f}")
    print(f"  Score Neutro: {combined.value['hold_score']:.2f}")
    
    print()


def main():
    """Função principal de teste."""
    print("🧪 TESTE DOS INDICADORES TÉCNICOS 🧪")
    print("=" * 50)
    print()
    
    try:
        test_rsi()
        test_macd()
        test_bollinger_bands()
        test_moving_averages()
        test_combined_signals()
        
        print("✅ Todos os testes concluídos com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

