"""
Bot de Sinais de Trading.

Este módulo implementa o bot principal para geração de sinais de trading
baseados em análise técnica de criptomoedas.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..config.settings import get_settings
from ..config.logging_config import get_logger, log_signal_generated, log_performance_metrics
from ..core.coinbase_client import CoinbaseClient
from ..core.exceptions import CryptoBotsException, InsufficientDataException
from .analyzers.trend_analyzer import TrendAnalyzer, TrendAnalysis
from .notifiers.console_notifier import NotificationManager

logger = get_logger(__name__)


@dataclass
class SignalResult:
    """Resultado de um sinal gerado."""
    symbol: str
    analysis: TrendAnalysis
    description: Dict[str, Any]
    timestamp: datetime


class SignalBot:
    """
    Bot principal para geração de sinais de trading.
    
    Monitora múltiplos pares de criptomoedas, executa análise técnica
    e gera sinais de trading com notificações automáticas.
    """
    
    def __init__(self, coinbase_client: Optional[CoinbaseClient] = None):
        """
        Inicializa o bot de sinais.
        
        Args:
            coinbase_client: Cliente Coinbase (opcional)
        """
        self.settings = get_settings()
        self.coinbase_client = coinbase_client or CoinbaseClient()
        self.trend_analyzer = TrendAnalyzer()
        self.notification_manager = NotificationManager()
        
        # Configurações do bot
        self.trading_pairs = self.settings.trading_pairs
        self.update_interval = self.settings.signal_update_interval
        self.min_volume_threshold = self.settings.min_volume_threshold
        self.signal_strength_threshold = self.settings.signal_strength_threshold
        
        # Estado interno
        self.is_running = False
        self.last_signals: Dict[str, SignalResult] = {}
        self.performance_metrics: Dict[str, Any] = {
            "signals_generated": 0,
            "notifications_sent": 0,
            "errors": 0,
            "uptime_start": datetime.now()
        }
        
        logger.info(
            "Signal bot initialized",
            trading_pairs=self.trading_pairs,
            update_interval=self.update_interval,
            min_volume_threshold=self.min_volume_threshold,
            signal_strength_threshold=self.signal_strength_threshold
        )
    
    async def start(self) -> None:
        """Inicia o bot de sinais."""
        if self.is_running:
            logger.warning("Signal bot is already running")
            return
        
        self.is_running = True
        self.performance_metrics["uptime_start"] = datetime.now()
        
        logger.info("Starting signal bot")
        
        # Verificar conexão com a API
        if not self.coinbase_client.test_connection():
            raise CryptoBotsException("Failed to connect to Coinbase API")
        
        # Enviar notificação de início
        await self._send_startup_notification()
        
        try:
            # Loop principal
            while self.is_running:
                start_time = time.time()
                
                try:
                    await self._process_signals()
                    
                    # Métricas de performance
                    processing_time = time.time() - start_time
                    log_performance_metrics(
                        logger,
                        component="signal_bot",
                        operation="process_signals",
                        duration=processing_time,
                        success=True
                    )
                    
                except Exception as e:
                    self.performance_metrics["errors"] += 1
                    processing_time = time.time() - start_time
                    
                    log_performance_metrics(
                        logger,
                        component="signal_bot",
                        operation="process_signals",
                        duration=processing_time,
                        success=False,
                        error=str(e)
                    )
                    
                    logger.error("Error processing signals", error=str(e))
                
                # Aguardar próximo ciclo
                await asyncio.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("Signal bot stopped by user")
        except Exception as e:
            logger.error("Signal bot crashed", error=str(e))
            raise
        finally:
            self.is_running = False
            await self._send_shutdown_notification()
    
    async def stop(self) -> None:
        """Para o bot de sinais."""
        logger.info("Stopping signal bot")
        self.is_running = False
    
    async def _process_signals(self) -> None:
        """Processa sinais para todos os pares de trading."""
        tasks = []
        
        for symbol in self.trading_pairs:
            task = asyncio.create_task(self._analyze_symbol(symbol))
            tasks.append(task)
        
        # Executar análises em paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processar resultados
        for i, result in enumerate(results):
            symbol = self.trading_pairs[i]
            
            if isinstance(result, Exception):
                logger.error(f"Error analyzing {symbol}", error=str(result))
                continue
            
            if result:
                await self._handle_signal(result)
    
    async def _analyze_symbol(self, symbol: str) -> Optional[SignalResult]:
        """
        Analisa um símbolo específico.
        
        Args:
            symbol: Par de trading (ex: BTC-USD)
            
        Returns:
            Resultado do sinal ou None se não há sinal
        """
        try:
            # Obter dados históricos
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)  # Últimas 24 horas
            
            candles = self.coinbase_client.get_product_candles(
                product_id=symbol,
                start=start_time,
                end=end_time,
                granularity="ONE_MINUTE"
            )
            logger.debug(candles)
            # Verificar se há candles suficientes
            if not candles or len(candles) < 100:
                logger.warning(f"Insufficient data for {symbol}", candles_count=len(candles) if candles else 0)
                return None
            
            # Converter dados para formato esperado
            prices = self._convert_candles_to_prices(candles)
            
            # Verificar volume mínimo
            if not self._check_volume_threshold(candles):
                logger.debug(f"Volume below threshold for {symbol}")
                return None
            
            # Executar análise
            analysis = self.trend_analyzer.analyze(prices)
            
            # Verificar se o sinal atende aos critérios
            if analysis.confidence < self.signal_strength_threshold:
                logger.debug(
                    f"Signal strength below threshold for {symbol}",
                    confidence=analysis.confidence,
                    threshold=self.signal_strength_threshold
                )
                return None
            
            # Verificar se é um novo sinal (evitar spam)
            if not self._is_new_signal(symbol, analysis):
                logger.debug(f"Signal not new for {symbol}")
                return None
            
            # Gerar descrição do sinal
            description = self.trend_analyzer.get_signal_description(analysis)
            
            signal_result = SignalResult(
                symbol=symbol,
                analysis=analysis,
                description=description,
                timestamp=datetime.now()
            )
            
            # Log do sinal gerado
            log_signal_generated(
                logger,
                signal_type=analysis.signal.value,
                symbol=symbol,
                strength=analysis.strength,
                indicators={
                    name: {
                        "signal": ind.signal.value,
                        "strength": ind.strength,
                        "value": ind.value
                    }
                    for name, ind in analysis.indicators.items()
                }
            )
            
            self.performance_metrics["signals_generated"] += 1
            
            return signal_result
            
        except InsufficientDataException as e:
            logger.warning(f"Insufficient data for {symbol}", error=str(e))
            return None
        except Exception as e:
            logger.error(f"Error analyzing {symbol}", error=str(e))
            return None
    
    def _convert_candles_to_prices(self, candles: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """
        Converte dados de candles para formato de preços.
        
        Args:
            candles: Lista de candles da API
            
        Returns:
            Dicionário com listas de preços
        """
        # Ordenar candles por timestamp (mais antigo primeiro)
        sorted_candles = sorted(candles, key=lambda x: int(x.get('start', 0)))
        
        prices = {
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': []
        }
        
        for candle in sorted_candles:
            prices['open'].append(float(candle.get('open', 0)))
            prices['high'].append(float(candle.get('high', 0)))
            prices['low'].append(float(candle.get('low', 0)))
            prices['close'].append(float(candle.get('close', 0)))
            prices['volume'].append(float(candle.get('volume', 0)))
        
        return prices
    
    def _check_volume_threshold(self, candles: List[Dict[str, Any]]) -> bool:
        """
        Verifica se o volume atende ao threshold mínimo.
        
        Args:
            candles: Lista de candles
            
        Returns:
            True se o volume é suficiente
        """
        if not candles:
            return False
        
        # Calcular volume médio das últimas 24 horas
        total_volume = sum(float(candle.get('volume', 0)) for candle in candles)
        avg_volume = total_volume / len(candles) if candles else 0
        
        return avg_volume >= self.min_volume_threshold
    
    def _is_new_signal(self, symbol: str, analysis: TrendAnalysis) -> bool:
        """
        Verifica se é um novo sinal (evita spam).
        
        Args:
            symbol: Par de trading
            analysis: Análise atual
            
        Returns:
            True se é um novo sinal
        """
        if symbol not in self.last_signals:
            return True
        
        last_signal = self.last_signals[symbol]
        
        # Verificar se mudou o tipo de sinal
        if last_signal.analysis.signal != analysis.signal:
            return True
        
        # Verificar se passou tempo suficiente (evitar spam)
        time_diff = datetime.now() - last_signal.timestamp
        if time_diff.total_seconds() < 300:  # 5 minutos
            return False
        
        # Verificar se a confiança aumentou significativamente
        confidence_diff = analysis.confidence - last_signal.analysis.confidence
        if confidence_diff > 0.2:  # 20% de aumento na confiança
            return True
        
        return False
    
    async def _handle_signal(self, signal_result: SignalResult) -> None:
        """
        Processa um sinal gerado.
        
        Args:
            signal_result: Resultado do sinal
        """
        symbol = signal_result.symbol
        analysis = signal_result.analysis
        description = signal_result.description
        
        # Salvar último sinal
        self.last_signals[symbol] = signal_result
        
        # Enviar notificação
        try:
            success = self.notification_manager.send_signal_notification(symbol, description)
            if success:
                self.performance_metrics["notifications_sent"] += 1
                logger.info(
                    "Signal notification sent",
                    symbol=symbol,
                    signal=analysis.signal.value,
                    confidence=analysis.confidence
                )
            else:
                logger.warning("Failed to send signal notification", symbol=symbol)
        except Exception as e:
            logger.error("Error sending notification", symbol=symbol, error=str(e))
    
    async def _send_startup_notification(self) -> None:
        """Envia notificação de inicialização."""
        message = f"🤖 Bot de Sinais Iniciado\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📊 Pares monitorados: {', '.join(self.trading_pairs)}\n"
        message += f"⏱️ Intervalo de atualização: {self.update_interval}s\n"
        message += f"🎯 Threshold de confiança: {self.signal_strength_threshold * 100}%\n"
        message += f"📈 Threshold de volume: {self.min_volume_threshold:,.0f}\n"
        message += f"🕐 Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.notification_manager.send_custom_notification(message)
    
    async def _send_shutdown_notification(self) -> None:
        """Envia notificação de encerramento."""
        uptime = datetime.now() - self.performance_metrics["uptime_start"]
        
        message = f"🛑 Bot de Sinais Encerrado\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"⏱️ Tempo de execução: {str(uptime).split('.')[0]}\n"
        message += f"📊 Sinais gerados: {self.performance_metrics['signals_generated']}\n"
        message += f"📨 Notificações enviadas: {self.performance_metrics['notifications_sent']}\n"
        message += f"❌ Erros: {self.performance_metrics['errors']}\n"
        message += f"🕐 Encerrado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.notification_manager.send_custom_notification(message)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual do bot.
        
        Returns:
            Status do bot
        """
        uptime = datetime.now() - self.performance_metrics["uptime_start"]
        
        return {
            "is_running": self.is_running,
            "uptime": str(uptime).split('.')[0],
            "trading_pairs": self.trading_pairs,
            "update_interval": self.update_interval,
            "performance_metrics": self.performance_metrics.copy(),
            "last_signals": {
                symbol: {
                    "signal": result.analysis.signal.value,
                    "confidence": result.analysis.confidence,
                    "timestamp": result.timestamp.isoformat()
                }
                for symbol, result in self.last_signals.items()
            }
        }
    
    async def analyze_single_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analisa um único símbolo sob demanda.
        
        Args:
            symbol: Par de trading
            
        Returns:
            Análise do símbolo ou None
        """
        try:
            signal_result = await self._analyze_symbol(symbol)
            
            if signal_result:
                return {
                    "symbol": symbol,
                    "analysis": signal_result.description,
                    "timestamp": signal_result.timestamp.isoformat()
                }
            else:
                return {
                    "symbol": symbol,
                    "analysis": None,
                    "message": "No signal generated (insufficient data or below threshold)",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in single symbol analysis for {symbol}", error=str(e))
            return {
                "symbol": symbol,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

