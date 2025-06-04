"""
Indicadores técnicos para análise de mercado.

Este módulo implementa os principais indicadores técnicos usados
em análise de trading, incluindo RSI, MACD, Bollinger Bands,
médias móveis e outros.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum

from ...config.logging_config import get_logger
from ...core.exceptions import InvalidIndicatorException, InsufficientDataException

logger = get_logger(__name__)


class SignalType(Enum):
    """Tipos de sinais de trading."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


@dataclass
class IndicatorResult:
    """Resultado de um indicador técnico."""
    value: Union[float, Dict[str, float]]
    signal: SignalType
    strength: float  # 0.0 a 1.0
    metadata: Dict[str, any]


class TechnicalIndicators:
    """
    Classe principal para cálculo de indicadores técnicos.
    
    Implementa os principais indicadores usados em análise técnica,
    com suporte a diferentes timeframes e configurações.
    """
    
    @staticmethod
    def validate_data(data: Union[List[float], pd.Series], min_periods: int) -> pd.Series:
        """
        Valida e converte dados para pandas Series.
        
        Args:
            data: Dados de preço
            min_periods: Número mínimo de períodos necessários
            
        Returns:
            Dados como pandas Series
            
        Raises:
            InsufficientDataException: Se não há dados suficientes
            InvalidIndicatorException: Se os dados são inválidos
        """
        if isinstance(data, list):
            data = pd.Series(data)
        
        if len(data) < min_periods:
            raise InsufficientDataException(min_periods, len(data))
        
        if data.isnull().any():
            logger.warning("Data contains null values, forward filling")
            data = data.fillna(method='ffill')
        
        return data
    
    @staticmethod
    def rsi(
        prices: Union[List[float], pd.Series],
        period: int = 14,
        overbought: float = 70,
        oversold: float = 30
    ) -> IndicatorResult:
        """
        Calcula o Relative Strength Index (RSI).
        
        Args:
            prices: Preços de fechamento
            period: Período para cálculo
            overbought: Nível de sobrecompra
            oversold: Nível de sobrevenda
            
        Returns:
            Resultado do RSI
        """
        prices = TechnicalIndicators.validate_data(prices, period + 1)
        
        # Calcular mudanças de preço
        delta = prices.diff()
        
        # Separar ganhos e perdas
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calcular médias móveis exponenciais
        avg_gains = gains.ewm(span=period).mean()
        avg_losses = losses.ewm(span=period).mean()
        
        # Calcular RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # Determinar sinal
        if current_rsi >= overbought:
            signal = SignalType.SELL
            strength = min((current_rsi - overbought) / (100 - overbought), 1.0)
        elif current_rsi <= oversold:
            signal = SignalType.BUY
            strength = min((oversold - current_rsi) / oversold, 1.0)
        else:
            signal = SignalType.HOLD
            # Força baseada na distância dos níveis extremos
            distance_to_extreme = min(
                abs(current_rsi - overbought),
                abs(current_rsi - oversold)
            )
            strength = 1.0 - (distance_to_extreme / 50.0)
        
        return IndicatorResult(
            value=current_rsi,
            signal=signal,
            strength=strength,
            metadata={
                "period": period,
                "overbought": overbought,
                "oversold": oversold,
                "rsi_series": rsi.tolist()
            }
        )
    
    @staticmethod
    def macd(
        prices: Union[List[float], pd.Series],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> IndicatorResult:
        """
        Calcula o MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: Preços de fechamento
            fast_period: Período da EMA rápida
            slow_period: Período da EMA lenta
            signal_period: Período da linha de sinal
            
        Returns:
            Resultado do MACD
        """
        prices = TechnicalIndicators.validate_data(prices, slow_period + signal_period)
        
        # Calcular EMAs
        ema_fast = prices.ewm(span=fast_period).mean()
        ema_slow = prices.ewm(span=slow_period).mean()
        
        # Calcular MACD line
        macd_line = ema_fast - ema_slow
        
        # Calcular Signal line
        signal_line = macd_line.ewm(span=signal_period).mean()
        
        # Calcular Histogram
        histogram = macd_line - signal_line
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_histogram = histogram.iloc[-1]
        previous_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0
        
        # Determinar sinal
        if current_macd > current_signal and current_histogram > 0:
            if current_histogram > previous_histogram:
                signal = SignalType.BUY
                strength = min(abs(current_histogram) / abs(current_macd), 1.0)
            else:
                signal = SignalType.HOLD
                strength = 0.3
        elif current_macd < current_signal and current_histogram < 0:
            if current_histogram < previous_histogram:
                signal = SignalType.SELL
                strength = min(abs(current_histogram) / abs(current_macd), 1.0)
            else:
                signal = SignalType.HOLD
                strength = 0.3
        else:
            signal = SignalType.HOLD
            strength = 0.1
        
        return IndicatorResult(
            value={
                "macd": current_macd,
                "signal": current_signal,
                "histogram": current_histogram
            },
            signal=signal,
            strength=strength,
            metadata={
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period,
                "macd_series": macd_line.tolist(),
                "signal_series": signal_line.tolist(),
                "histogram_series": histogram.tolist()
            }
        )
    
    @staticmethod
    def bollinger_bands(
        prices: Union[List[float], pd.Series],
        period: int = 20,
        std_dev: float = 2.0
    ) -> IndicatorResult:
        """
        Calcula as Bollinger Bands.
        
        Args:
            prices: Preços de fechamento
            period: Período para média móvel
            std_dev: Número de desvios padrão
            
        Returns:
            Resultado das Bollinger Bands
        """
        prices = TechnicalIndicators.validate_data(prices, period)
        
        # Calcular média móvel simples
        sma = prices.rolling(window=period).mean()
        
        # Calcular desvio padrão
        std = prices.rolling(window=period).std()
        
        # Calcular bandas
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        current_price = prices.iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        current_middle = sma.iloc[-1]
        
        # Calcular posição do preço nas bandas (0 = banda inferior, 1 = banda superior)
        band_width = current_upper - current_lower
        price_position = (current_price - current_lower) / band_width if band_width > 0 else 0.5
        
        # Determinar sinal
        if price_position >= 0.9:  # Próximo da banda superior
            signal = SignalType.SELL
            strength = min((price_position - 0.9) / 0.1, 1.0)
        elif price_position <= 0.1:  # Próximo da banda inferior
            signal = SignalType.BUY
            strength = min((0.1 - price_position) / 0.1, 1.0)
        else:
            signal = SignalType.HOLD
            # Força baseada na distância do centro
            distance_from_center = abs(price_position - 0.5)
            strength = distance_from_center * 2  # Normalizar para 0-1
        
        return IndicatorResult(
            value={
                "upper": current_upper,
                "middle": current_middle,
                "lower": current_lower,
                "position": price_position
            },
            signal=signal,
            strength=strength,
            metadata={
                "period": period,
                "std_dev": std_dev,
                "band_width": band_width,
                "upper_series": upper_band.tolist(),
                "middle_series": sma.tolist(),
                "lower_series": lower_band.tolist()
            }
        )
    
    @staticmethod
    def moving_averages(
        prices: Union[List[float], pd.Series],
        short_period: int = 10,
        long_period: int = 50
    ) -> IndicatorResult:
        """
        Calcula médias móveis simples e determina crossover.
        
        Args:
            prices: Preços de fechamento
            short_period: Período da média curta
            long_period: Período da média longa
            
        Returns:
            Resultado das médias móveis
        """
        prices = TechnicalIndicators.validate_data(prices, long_period)
        
        # Calcular médias móveis
        sma_short = prices.rolling(window=short_period).mean()
        sma_long = prices.rolling(window=long_period).mean()
        
        current_short = sma_short.iloc[-1]
        current_long = sma_long.iloc[-1]
        previous_short = sma_short.iloc[-2] if len(sma_short) > 1 else current_short
        previous_long = sma_long.iloc[-2] if len(sma_long) > 1 else current_long
        
        # Verificar crossover
        current_above = current_short > current_long
        previous_above = previous_short > previous_long
        
        # Calcular divergência percentual
        divergence = abs(current_short - current_long) / current_long * 100
        
        # Determinar sinal
        if current_above and not previous_above:  # Golden cross
            signal = SignalType.BUY
            strength = min(divergence / 5.0, 1.0)  # Normalizar baseado em 5% de divergência
        elif not current_above and previous_above:  # Death cross
            signal = SignalType.SELL
            strength = min(divergence / 5.0, 1.0)
        elif current_above:  # Tendência de alta
            signal = SignalType.HOLD
            strength = min(divergence / 10.0, 0.7)
        else:  # Tendência de baixa
            signal = SignalType.HOLD
            strength = min(divergence / 10.0, 0.7)
        
        return IndicatorResult(
            value={
                "short_ma": current_short,
                "long_ma": current_long,
                "divergence": divergence
            },
            signal=signal,
            strength=strength,
            metadata={
                "short_period": short_period,
                "long_period": long_period,
                "crossover": current_above != previous_above,
                "trend": "bullish" if current_above else "bearish",
                "short_series": sma_short.tolist(),
                "long_series": sma_long.tolist()
            }
        )
    
    @staticmethod
    def stochastic_oscillator(
        high_prices: Union[List[float], pd.Series],
        low_prices: Union[List[float], pd.Series],
        close_prices: Union[List[float], pd.Series],
        k_period: int = 14,
        d_period: int = 3,
        overbought: float = 80,
        oversold: float = 20
    ) -> IndicatorResult:
        """
        Calcula o Oscilador Estocástico.
        
        Args:
            high_prices: Preços máximos
            low_prices: Preços mínimos
            close_prices: Preços de fechamento
            k_period: Período para %K
            d_period: Período para %D
            overbought: Nível de sobrecompra
            oversold: Nível de sobrevenda
            
        Returns:
            Resultado do Estocástico
        """
        high_prices = TechnicalIndicators.validate_data(high_prices, k_period)
        low_prices = TechnicalIndicators.validate_data(low_prices, k_period)
        close_prices = TechnicalIndicators.validate_data(close_prices, k_period)
        
        # Calcular %K
        lowest_low = low_prices.rolling(window=k_period).min()
        highest_high = high_prices.rolling(window=k_period).max()
        
        k_percent = 100 * (close_prices - lowest_low) / (highest_high - lowest_low)
        
        # Calcular %D (média móvel de %K)
        d_percent = k_percent.rolling(window=d_period).mean()
        
        current_k = k_percent.iloc[-1]
        current_d = d_percent.iloc[-1]
        
        # Determinar sinal
        if current_k >= overbought and current_d >= overbought:
            signal = SignalType.SELL
            strength = min((current_k - overbought) / (100 - overbought), 1.0)
        elif current_k <= oversold and current_d <= oversold:
            signal = SignalType.BUY
            strength = min((oversold - current_k) / oversold, 1.0)
        elif current_k > current_d:  # %K acima de %D
            signal = SignalType.HOLD
            strength = 0.3
        else:
            signal = SignalType.HOLD
            strength = 0.1
        
        return IndicatorResult(
            value={
                "k_percent": current_k,
                "d_percent": current_d
            },
            signal=signal,
            strength=strength,
            metadata={
                "k_period": k_period,
                "d_period": d_period,
                "overbought": overbought,
                "oversold": oversold,
                "k_series": k_percent.tolist(),
                "d_series": d_percent.tolist()
            }
        )
    
    @staticmethod
    def williams_r(
        high_prices: Union[List[float], pd.Series],
        low_prices: Union[List[float], pd.Series],
        close_prices: Union[List[float], pd.Series],
        period: int = 14,
        overbought: float = -20,
        oversold: float = -80
    ) -> IndicatorResult:
        """
        Calcula o Williams %R.
        
        Args:
            high_prices: Preços máximos
            low_prices: Preços mínimos
            close_prices: Preços de fechamento
            period: Período para cálculo
            overbought: Nível de sobrecompra
            oversold: Nível de sobrevenda
            
        Returns:
            Resultado do Williams %R
        """
        high_prices = TechnicalIndicators.validate_data(high_prices, period)
        low_prices = TechnicalIndicators.validate_data(low_prices, period)
        close_prices = TechnicalIndicators.validate_data(close_prices, period)
        
        # Calcular Williams %R
        highest_high = high_prices.rolling(window=period).max()
        lowest_low = low_prices.rolling(window=period).min()
        
        williams_r = -100 * (highest_high - close_prices) / (highest_high - lowest_low)
        
        current_wr = williams_r.iloc[-1]
        
        # Determinar sinal
        if current_wr >= overbought:
            signal = SignalType.SELL
            strength = min((current_wr - overbought) / (0 - overbought), 1.0)
        elif current_wr <= oversold:
            signal = SignalType.BUY
            strength = min((oversold - current_wr) / (oversold - (-100)), 1.0)
        else:
            signal = SignalType.HOLD
            # Força baseada na distância dos níveis extremos
            distance_to_extreme = min(
                abs(current_wr - overbought),
                abs(current_wr - oversold)
            )
            strength = 1.0 - (distance_to_extreme / 40.0)  # Normalizar para range de 80
        
        return IndicatorResult(
            value=current_wr,
            signal=signal,
            strength=strength,
            metadata={
                "period": period,
                "overbought": overbought,
                "oversold": oversold,
                "williams_r_series": williams_r.tolist()
            }
        )
    
    @staticmethod
    def combine_signals(indicators: List[IndicatorResult], weights: Optional[List[float]] = None) -> IndicatorResult:
        """
        Combina múltiplos sinais de indicadores em um sinal consolidado.
        
        Args:
            indicators: Lista de resultados de indicadores
            weights: Pesos para cada indicador (opcional)
            
        Returns:
            Sinal combinado
        """
        if not indicators:
            raise InvalidIndicatorException("combine_signals", "No indicators provided")
        
        if weights is None:
            weights = [1.0] * len(indicators)
        
        if len(weights) != len(indicators):
            raise InvalidIndicatorException("combine_signals", "Weights length must match indicators length")
        
        # Normalizar pesos
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # Calcular scores para cada tipo de sinal
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        
        for indicator, weight in zip(indicators, weights):
            weighted_strength = indicator.strength * weight
            
            if indicator.signal in [SignalType.BUY, SignalType.STRONG_BUY]:
                buy_score += weighted_strength
            elif indicator.signal in [SignalType.SELL, SignalType.STRONG_SELL]:
                sell_score += weighted_strength
            else:
                hold_score += weighted_strength
        
        # Determinar sinal final
        max_score = max(buy_score, sell_score, hold_score)
        
        if max_score == buy_score and buy_score > 0.6:
            final_signal = SignalType.STRONG_BUY if buy_score > 0.8 else SignalType.BUY
        elif max_score == sell_score and sell_score > 0.6:
            final_signal = SignalType.STRONG_SELL if sell_score > 0.8 else SignalType.SELL
        else:
            final_signal = SignalType.HOLD
        
        return IndicatorResult(
            value={
                "buy_score": buy_score,
                "sell_score": sell_score,
                "hold_score": hold_score
            },
            signal=final_signal,
            strength=max_score,
            metadata={
                "individual_signals": [
                    {
                        "signal": ind.signal.value,
                        "strength": ind.strength,
                        "weight": weight
                    }
                    for ind, weight in zip(indicators, weights)
                ],
                "weights": weights
            }
        )

