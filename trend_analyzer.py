"""
Analisador de tendências de mercado.

Este módulo implementa análise de tendências usando indicadores técnicos
para identificar direções de mercado e gerar sinais de trading.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from ...config.settings import get_settings
from ...config.logging_config import get_logger
from ...core.exceptions import InsufficientDataException, InvalidIndicatorException
from ..indicators.technical_indicators import TechnicalIndicators, SignalType, IndicatorResult

logger = get_logger(__name__)


@dataclass
class TrendAnalysis:
    """Resultado da análise de tendência."""
    trend: str  # bullish, bearish, sideways
    strength: float  # 0.0 a 1.0
    signal: SignalType
    confidence: float  # 0.0 a 1.0
    indicators: Dict[str, IndicatorResult]
    timestamp: datetime


class TrendAnalyzer:
    """
    Analisador de tendências de mercado.
    
    Combina múltiplos indicadores técnicos para identificar tendências
    e gerar sinais de trading com níveis de confiança.
    """
    
    def __init__(self):
        """Inicializa o analisador de tendências."""
        self.settings = get_settings()
        self.indicators = TechnicalIndicators()
        
        # Configurações dos indicadores
        self.rsi_period = self.settings.rsi_period
        self.rsi_overbought = self.settings.rsi_overbought
        self.rsi_oversold = self.settings.rsi_oversold
        
        self.macd_fast = self.settings.macd_fast
        self.macd_slow = self.settings.macd_slow
        self.macd_signal = self.settings.macd_signal
        
        self.bb_period = self.settings.bb_period
        self.bb_std = self.settings.bb_std
        
        self.ma_short = self.settings.ma_short
        self.ma_long = self.settings.ma_long
        
        logger.info(
            "Trend analyzer initialized",
            rsi_period=self.rsi_period,
            macd_fast=self.macd_fast,
            macd_slow=self.macd_slow,
            bb_period=self.bb_period,
            ma_short=self.ma_short,
            ma_long=self.ma_long
        )
    
    def analyze(
        self,
        prices: Dict[str, List[float]],
        volumes: Optional[List[float]] = None,
        timestamp: Optional[datetime] = None
    ) -> TrendAnalysis:
        """
        Analisa tendências de mercado com base em dados históricos.
        
        Args:
            prices: Dicionário com preços (open, high, low, close)
            volumes: Volumes de negociação (opcional)
            timestamp: Timestamp da análise (opcional)
            
        Returns:
            Análise de tendência
            
        Raises:
            InsufficientDataException: Se não há dados suficientes
        """
        if not prices or not prices.get('close'):
            raise InsufficientDataException(1, 0)
        
        close_prices = prices['close']
        high_prices = prices.get('high', close_prices)
        low_prices = prices.get('low', close_prices)
        open_prices = prices.get('open', close_prices)
        
        # Timestamp padrão
        if timestamp is None:
            timestamp = datetime.now()
        
        # Calcular indicadores
        indicators_results = {}
        
        try:
            # RSI
            indicators_results['rsi'] = TechnicalIndicators.rsi(
                close_prices,
                period=self.rsi_period,
                overbought=self.rsi_overbought,
                oversold=self.rsi_oversold
            )
            
            # MACD
            indicators_results['macd'] = TechnicalIndicators.macd(
                close_prices,
                fast_period=self.macd_fast,
                slow_period=self.macd_slow,
                signal_period=self.macd_signal
            )
            
            # Bollinger Bands
            indicators_results['bollinger'] = TechnicalIndicators.bollinger_bands(
                close_prices,
                period=self.bb_period,
                std_dev=self.bb_std
            )
            
            # Moving Averages
            indicators_results['moving_averages'] = TechnicalIndicators.moving_averages(
                close_prices,
                short_period=self.ma_short,
                long_period=self.ma_long
            )
            
            # Adicionar mais indicadores se volumes disponíveis
            if volumes and len(volumes) >= 14:
                # Stochastic Oscillator
                indicators_results['stochastic'] = TechnicalIndicators.stochastic_oscillator(
                    high_prices,
                    low_prices,
                    close_prices
                )
                
                # Williams %R
                indicators_results['williams_r'] = TechnicalIndicators.williams_r(
                    high_prices,
                    low_prices,
                    close_prices
                )
        
        except Exception as e:
            logger.error("Error calculating indicators", error=str(e))
            raise InvalidIndicatorException("analyze", str(e))
        
        # Combinar sinais com pesos
        weights = {
            'rsi': 1.0,
            'macd': 1.5,
            'bollinger': 1.0,
            'moving_averages': 2.0,
            'stochastic': 0.8,
            'williams_r': 0.7
        }
        
        # Filtrar apenas indicadores disponíveis
        available_indicators = [indicators_results[k] for k in indicators_results.keys()]
        available_weights = [weights[k] for k in indicators_results.keys()]
        
        # Combinar sinais
        combined_signal = TechnicalIndicators.combine_signals(
            available_indicators,
            available_weights
        )
        
        # Determinar tendência
        trend, trend_strength = self._determine_trend(
            close_prices,
            indicators_results,
            combined_signal
        )
        
        # Calcular confiança
        confidence = self._calculate_confidence(
            indicators_results,
            combined_signal,
            trend_strength
        )
        
        return TrendAnalysis(
            trend=trend,
            strength=trend_strength,
            signal=combined_signal.signal,
            confidence=confidence,
            indicators=indicators_results,
            timestamp=timestamp
        )
    
    def _determine_trend(
        self,
        prices: List[float],
        indicators: Dict[str, IndicatorResult],
        combined_signal: IndicatorResult
    ) -> Tuple[str, float]:
        """
        Determina a tendência do mercado.
        
        Args:
            prices: Preços de fechamento
            indicators: Resultados dos indicadores
            combined_signal: Sinal combinado
            
        Returns:
            Tupla com (tendência, força)
        """
        # Verificar tendência de médias móveis
        ma_trend = "sideways"
        ma_strength = 0.5
        
        if 'moving_averages' in indicators:
            ma_result = indicators['moving_averages']
            ma_values = ma_result.value
            
            if ma_values['short_ma'] > ma_values['long_ma']:
                ma_trend = "bullish"
                ma_strength = min(ma_values['divergence'] / 5.0, 1.0)
            elif ma_values['short_ma'] < ma_values['long_ma']:
                ma_trend = "bearish"
                ma_strength = min(ma_values['divergence'] / 5.0, 1.0)
        
        # Verificar tendência de preços recentes
        price_trend = "sideways"
        price_strength = 0.5
        
        if len(prices) >= 10:
            recent_prices = prices[-10:]
            price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
            
            if price_change > 1.0:  # 1% de aumento
                price_trend = "bullish"
                price_strength = min(price_change / 5.0, 1.0)
            elif price_change < -1.0:  # 1% de queda
                price_trend = "bearish"
                price_strength = min(abs(price_change) / 5.0, 1.0)
        
        # Combinar tendências
        if ma_trend == price_trend:
            final_trend = ma_trend
            final_strength = (ma_strength + price_strength) / 2
        elif ma_strength > price_strength:
            final_trend = ma_trend
            final_strength = ma_strength * 0.7 + price_strength * 0.3
        else:
            final_trend = price_trend
            final_strength = price_strength * 0.7 + ma_strength * 0.3
        
        # Ajustar com base no sinal combinado
        if combined_signal.signal in [SignalType.BUY, SignalType.STRONG_BUY] and final_trend == "bearish":
            final_trend = "sideways"
            final_strength = 0.5
        elif combined_signal.signal in [SignalType.SELL, SignalType.STRONG_SELL] and final_trend == "bullish":
            final_trend = "sideways"
            final_strength = 0.5
        
        return final_trend, final_strength
    
    def _calculate_confidence(
        self,
        indicators: Dict[str, IndicatorResult],
        combined_signal: IndicatorResult,
        trend_strength: float
    ) -> float:
        """
        Calcula o nível de confiança do sinal.
        
        Args:
            indicators: Resultados dos indicadores
            combined_signal: Sinal combinado
            trend_strength: Força da tendência
            
        Returns:
            Nível de confiança (0.0 a 1.0)
        """
        # Contar quantos indicadores concordam com o sinal combinado
        agreeing_indicators = 0
        total_indicators = len(indicators)
        
        for indicator in indicators.values():
            if indicator.signal == combined_signal.signal:
                agreeing_indicators += 1
        
        # Calcular concordância
        agreement_ratio = agreeing_indicators / total_indicators if total_indicators > 0 else 0
        
        # Combinar concordância com força do sinal e tendência
        confidence = (
            agreement_ratio * 0.4 +
            combined_signal.strength * 0.4 +
            trend_strength * 0.2
        )
        
        return min(confidence, 1.0)
    
    def get_signal_description(self, analysis: TrendAnalysis) -> Dict[str, Any]:
        """
        Gera uma descrição detalhada do sinal.
        
        Args:
            analysis: Análise de tendência
            
        Returns:
            Descrição do sinal
        """
        signal_type = analysis.signal.value
        confidence = analysis.confidence
        trend = analysis.trend
        strength = analysis.strength
        
        # Descrição do sinal
        if signal_type in ["buy", "strong_buy"]:
            action = "compra"
            if confidence > 0.8:
                confidence_desc = "alta"
            elif confidence > 0.6:
                confidence_desc = "moderada"
            else:
                confidence_desc = "baixa"
        elif signal_type in ["sell", "strong_sell"]:
            action = "venda"
            if confidence > 0.8:
                confidence_desc = "alta"
            elif confidence > 0.6:
                confidence_desc = "moderada"
            else:
                confidence_desc = "baixa"
        else:
            action = "neutro"
            confidence_desc = "moderada"
        
        # Descrição da tendência
        if trend == "bullish":
            trend_desc = "alta"
            if strength > 0.8:
                trend_strength_desc = "forte"
            elif strength > 0.5:
                trend_strength_desc = "moderada"
            else:
                trend_strength_desc = "fraca"
        elif trend == "bearish":
            trend_desc = "baixa"
            if strength > 0.8:
                trend_strength_desc = "forte"
            elif strength > 0.5:
                trend_strength_desc = "moderada"
            else:
                trend_strength_desc = "fraca"
        else:
            trend_desc = "lateral"
            trend_strength_desc = "indefinida"
        
        # Detalhes dos indicadores
        indicators_details = {}
        for name, indicator in analysis.indicators.items():
            if name == "rsi":
                value = indicator.value
                if value > 70:
                    status = "sobrecomprado"
                elif value < 30:
                    status = "sobrevendido"
                else:
                    status = "neutro"
                indicators_details["RSI"] = {
                    "valor": round(value, 2),
                    "status": status
                }
            elif name == "macd":
                value = indicator.value
                indicators_details["MACD"] = {
                    "linha_macd": round(value["macd"], 4),
                    "linha_sinal": round(value["signal"], 4),
                    "histograma": round(value["histogram"], 4)
                }
            elif name == "bollinger":
                value = indicator.value
                indicators_details["Bollinger"] = {
                    "banda_superior": round(value["upper"], 2),
                    "banda_media": round(value["middle"], 2),
                    "banda_inferior": round(value["lower"], 2),
                    "posicao": round(value["position"] * 100, 1)
                }
            elif name == "moving_averages":
                value = indicator.value
                indicators_details["Médias Móveis"] = {
                    "curta": round(value["short_ma"], 2),
                    "longa": round(value["long_ma"], 2),
                    "divergencia": round(value["divergence"], 2)
                }
        
        return {
            "sinal": signal_type,
            "acao_recomendada": action,
            "confianca": {
                "valor": round(confidence * 100, 1),
                "descricao": confidence_desc
            },
            "tendencia": {
                "direcao": trend_desc,
                "forca": {
                    "valor": round(strength * 100, 1),
                    "descricao": trend_strength_desc
                }
            },
            "indicadores": indicators_details,
            "timestamp": analysis.timestamp.isoformat()
        }

