"""
Testes de integração para os bots de criptomoedas.

Este módulo contém testes de integração que validam o funcionamento
completo dos bots de sinais e trading.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

from src.signals.signal_bot import SignalBot
from src.trading.trading_bot import TradingBot
from src.core.coinbase_client import CoinbaseClient
from src.trading.portfolio.portfolio_manager import PortfolioManager


class TestSignalBotIntegration(unittest.TestCase):
    """Testes de integração para o bot de sinais."""
    
    def setUp(self):
        """Configuração inicial."""
        # Mock do cliente Coinbase
        self.mock_client = Mock(spec=CoinbaseClient)
        self.mock_client.test_connection.return_value = True
        
        # Dados de candles mock
        self.mock_candles = [
            {
                'start': str(int((datetime.now() - timedelta(minutes=i)).timestamp())),
                'open': str(50000 + i * 10),
                'high': str(50100 + i * 10),
                'low': str(49900 + i * 10),
                'close': str(50050 + i * 10),
                'volume': str(1000 + i)
            }
            for i in range(100)
        ]
        
        self.mock_client.get_product_candles.return_value = self.mock_candles
        
        self.signal_bot = SignalBot(self.mock_client)
    
    def test_signal_bot_initialization(self):
        """Testa inicialização do bot de sinais."""
        self.assertIsNotNone(self.signal_bot.coinbase_client)
        self.assertIsNotNone(self.signal_bot.trend_analyzer)
        self.assertIsNotNone(self.signal_bot.notification_manager)
        self.assertFalse(self.signal_bot.is_running)
        self.assertEqual(len(self.signal_bot.last_signals), 0)
    
    async def test_analyze_single_symbol(self):
        """Testa análise de um único símbolo."""
        result = await self.signal_bot.analyze_single_symbol("BTC-USD")
        
        self.assertIsNotNone(result)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "BTC-USD")
        
        # Verificar se a API foi chamada
        self.mock_client.get_product_candles.assert_called()
    
    def test_convert_candles_to_prices(self):
        """Testa conversão de candles para preços."""
        prices = self.signal_bot._convert_candles_to_prices(self.mock_candles)
        
        self.assertIn('open', prices)
        self.assertIn('high', prices)
        self.assertIn('low', prices)
        self.assertIn('close', prices)
        self.assertIn('volume', prices)
        
        self.assertEqual(len(prices['close']), 100)
        self.assertIsInstance(prices['close'][0], float)
    
    def test_check_volume_threshold(self):
        """Testa verificação de threshold de volume."""
        # Volume alto - deve passar
        high_volume_candles = [
            {'volume': '2000000'} for _ in range(10)
        ]
        self.assertTrue(self.signal_bot._check_volume_threshold(high_volume_candles))
        
        # Volume baixo - não deve passar
        low_volume_candles = [
            {'volume': '100'} for _ in range(10)
        ]
        self.assertFalse(self.signal_bot._check_volume_threshold(low_volume_candles))
    
    def test_is_new_signal(self):
        """Testa verificação de novo sinal."""
        from src.signals.analyzers.trend_analyzer import TrendAnalysis
        from src.signals.indicators.technical_indicators import SignalType
        
        # Primeiro sinal - deve ser novo
        analysis = Mock()
        analysis.signal = SignalType.BUY
        analysis.confidence = 0.8
        
        self.assertTrue(self.signal_bot._is_new_signal("BTC-USD", analysis))
        
        # Adicionar sinal ao histórico
        from src.signals.signal_bot import SignalResult
        signal_result = SignalResult(
            symbol="BTC-USD",
            analysis=analysis,
            description={},
            timestamp=datetime.now()
        )
        self.signal_bot.last_signals["BTC-USD"] = signal_result
        
        # Mesmo sinal muito recente - não deve ser novo
        self.assertFalse(self.signal_bot._is_new_signal("BTC-USD", analysis))
        
        # Sinal antigo - deve ser novo
        signal_result.timestamp = datetime.now() - timedelta(minutes=10)
        self.assertTrue(self.signal_bot._is_new_signal("BTC-USD", analysis))
    
    def test_get_status(self):
        """Testa obtenção de status do bot."""
        status = self.signal_bot.get_status()
        
        self.assertIn("is_running", status)
        self.assertIn("uptime", status)
        self.assertIn("trading_pairs", status)
        self.assertIn("performance_metrics", status)
        self.assertIn("last_signals", status)
        
        self.assertFalse(status["is_running"])
        self.assertIsInstance(status["trading_pairs"], list)


class TestTradingBotIntegration(unittest.TestCase):
    """Testes de integração para o bot de trading."""
    
    def setUp(self):
        """Configuração inicial."""
        # Mock do cliente Coinbase
        self.mock_client = Mock(spec=CoinbaseClient)
        self.mock_client.test_connection.return_value = True
        self.mock_client.get_product_ticker.return_value = {
            'price': '50000.0',
            'volume': '1000000'
        }
        
        self.trading_bot = TradingBot(self.mock_client)
    
    def test_trading_bot_initialization(self):
        """Testa inicialização do bot de trading."""
        self.assertIsNotNone(self.trading_bot.coinbase_client)
        self.assertIsNotNone(self.trading_bot.signal_bot)
        self.assertIsNotNone(self.trading_bot.portfolio_manager)
        self.assertIsNotNone(self.trading_bot.risk_manager)
        self.assertIn("swing_trading", self.trading_bot.strategies)
        self.assertFalse(self.trading_bot.is_running)
    
    async def test_update_market_data(self):
        """Testa atualização de dados de mercado."""
        await self.trading_bot._update_market_data()
        
        # Verificar se dados foram atualizados
        for symbol in self.trading_bot.trading_pairs:
            self.assertIn(symbol, self.trading_bot.market_data_cache)
            data = self.trading_bot.market_data_cache[symbol]
            self.assertIn("price", data)
            self.assertIn("volume", data)
            self.assertIn("timestamp", data)
    
    async def test_update_position_prices(self):
        """Testa atualização de preços das posições."""
        # Adicionar posição mock ao portfólio
        from src.trading.strategies.base_strategy import Position
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=50000.0,
            timestamp=datetime.now()
        )
        
        self.trading_bot.portfolio_manager.positions["BTC-USD"] = position
        
        # Atualizar dados de mercado primeiro
        await self.trading_bot._update_market_data()
        
        # Atualizar preços das posições
        await self.trading_bot._update_position_prices()
        
        # Verificar se preço foi atualizado
        updated_position = self.trading_bot.portfolio_manager.positions["BTC-USD"]
        self.assertEqual(updated_position.current_price, 50000.0)
    
    def test_convert_to_trading_signal(self):
        """Testa conversão de resultado de sinal para TradingSignal."""
        signal_result = {
            "symbol": "BTC-USD",
            "analysis": {
                "sinal": "compra",
                "confianca": {"valor": 80},
                "tendencia": {
                    "forca": {"valor": 75}
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Adicionar preço ao cache
        self.trading_bot.market_data_cache["BTC-USD"] = {"price": 50000.0}
        
        trading_signal = self.trading_bot._convert_to_trading_signal("BTC-USD", signal_result)
        
        self.assertIsNotNone(trading_signal)
        self.assertEqual(trading_signal.symbol, "BTC-USD")
        self.assertEqual(trading_signal.entry_price, 50000.0)
        self.assertEqual(trading_signal.confidence, 0.8)
        self.assertEqual(trading_signal.strength, 0.75)
    
    async def test_simulate_order_execution(self):
        """Testa simulação de execução de ordem."""
        from src.trading.strategies.base_strategy import TradeOrder, OrderSide, OrderType
        
        order = TradeOrder(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            size=0.1,
            client_order_id="test_order_123",
            metadata={"strategy": "swing_trading"}
        )
        
        # Adicionar preço ao cache
        self.trading_bot.market_data_cache["BTC-USD"] = {"price": 50000.0}
        
        success = await self.trading_bot._simulate_order_execution(order)
        
        self.assertTrue(success)
        
        # Verificar se posição foi adicionada
        self.assertIn("BTC-USD", self.trading_bot.portfolio_manager.positions)
        position = self.trading_bot.portfolio_manager.positions["BTC-USD"]
        self.assertEqual(position.symbol, "BTC-USD")
        self.assertEqual(position.side, "buy")
        self.assertEqual(position.size, 0.1)
    
    async def test_close_position(self):
        """Testa fechamento de posição."""
        # Adicionar posição primeiro
        from src.trading.strategies.base_strategy import Position
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=52000.0,
            timestamp=datetime.now()
        )
        
        self.trading_bot.portfolio_manager.positions["BTC-USD"] = position
        self.trading_bot.strategies["swing_trading"].positions["BTC-USD"] = position
        
        # Adicionar preço ao cache
        self.trading_bot.market_data_cache["BTC-USD"] = {"price": 52000.0}
        
        await self.trading_bot._close_position("BTC-USD", "test", "swing_trading")
        
        # Verificar se posição foi removida
        self.assertNotIn("BTC-USD", self.trading_bot.portfolio_manager.positions)
        self.assertNotIn("BTC-USD", self.trading_bot.strategies["swing_trading"].positions)
    
    def test_get_status(self):
        """Testa obtenção de status do bot de trading."""
        status = self.trading_bot.get_status()
        
        self.assertIn("is_running", status)
        self.assertIn("dry_run", status)
        self.assertIn("trading_pairs", status)
        self.assertIn("performance_metrics", status)
        self.assertIn("portfolio_status", status)
        self.assertIn("strategies", status)
        self.assertIn("pending_orders", status)
        
        self.assertFalse(status["is_running"])
        self.assertTrue(status["dry_run"])
        self.assertIsInstance(status["strategies"], dict)
    
    def test_get_portfolio_summary(self):
        """Testa obtenção de resumo do portfólio."""
        summary = self.trading_bot.get_portfolio_summary()
        
        self.assertIn("portfolio_metrics", summary)
        self.assertIn("positions", summary)
        self.assertIn("recent_trades", summary)
        
        metrics = summary["portfolio_metrics"]
        self.assertIn("total_value", metrics)
        self.assertIn("total_pnl", metrics)
        self.assertIn("win_rate", metrics)


class TestPortfolioManagerIntegration(unittest.TestCase):
    """Testes de integração para o gerenciador de portfólio."""
    
    def setUp(self):
        """Configuração inicial."""
        self.portfolio = PortfolioManager(initial_balance=10000.0)
    
    def test_portfolio_initialization(self):
        """Testa inicialização do portfólio."""
        self.assertEqual(self.portfolio.account_balance.total_balance, 10000.0)
        self.assertEqual(self.portfolio.account_balance.available_balance, 10000.0)
        self.assertEqual(self.portfolio.account_balance.reserved_balance, 0.0)
        self.assertEqual(len(self.portfolio.positions), 0)
        self.assertEqual(len(self.portfolio.trade_history), 0)
    
    def test_add_and_close_position(self):
        """Testa adição e fechamento de posição."""
        from src.trading.strategies.base_strategy import Position
        
        # Adicionar posição
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=50000.0,
            timestamp=datetime.now()
        )
        
        success = self.portfolio.add_position(position)
        self.assertTrue(success)
        
        # Verificar saldos
        self.assertEqual(self.portfolio.account_balance.available_balance, 5000.0)  # 10000 - 5000
        self.assertEqual(self.portfolio.account_balance.reserved_balance, 5000.0)
        
        # Fechar posição com lucro
        pnl = self.portfolio.close_position("BTC-USD", 52000.0, "profit", "test_strategy")
        
        self.assertEqual(pnl, 200.0)  # (52000 - 50000) * 0.1
        self.assertEqual(self.portfolio.account_balance.total_balance, 10200.0)
        self.assertEqual(self.portfolio.total_trades, 1)
        self.assertEqual(self.portfolio.winning_trades, 1)
    
    def test_portfolio_metrics(self):
        """Testa cálculo de métricas do portfólio."""
        # Adicionar alguns trades
        from src.trading.strategies.base_strategy import Position
        
        # Trade vencedor
        position1 = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=50000.0,
            timestamp=datetime.now()
        )
        self.portfolio.add_position(position1)
        self.portfolio.close_position("BTC-USD", 52000.0, "profit", "test")
        
        # Trade perdedor
        position2 = Position(
            symbol="ETH-USD",
            side="buy",
            size=1.0,
            entry_price=3000.0,
            current_price=3000.0,
            timestamp=datetime.now()
        )
        self.portfolio.add_position(position2)
        self.portfolio.close_position("ETH-USD", 2800.0, "loss", "test")
        
        metrics = self.portfolio.get_portfolio_metrics()
        
        self.assertEqual(metrics.total_trades, 2)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertEqual(metrics.win_rate, 50.0)
        self.assertEqual(metrics.total_pnl, 0.0)  # 200 - 200 = 0
    
    def test_update_position_prices(self):
        """Testa atualização de preços das posições."""
        from src.trading.strategies.base_strategy import Position
        
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=50000.0,
            timestamp=datetime.now()
        )
        
        self.portfolio.add_position(position)
        
        # Atualizar preços
        self.portfolio.update_position_prices({"BTC-USD": 52000.0})
        
        updated_position = self.portfolio.positions["BTC-USD"]
        self.assertEqual(updated_position.current_price, 52000.0)
        self.assertEqual(updated_position.unrealized_pnl, 200.0)
    
    def test_get_unrealized_pnl(self):
        """Testa cálculo de P&L não realizado."""
        from src.trading.strategies.base_strategy import Position
        
        # Posição com lucro
        position1 = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=52000.0,
            timestamp=datetime.now()
        )
        position1.unrealized_pnl = 200.0
        
        # Posição com prejuízo
        position2 = Position(
            symbol="ETH-USD",
            side="buy",
            size=1.0,
            entry_price=3000.0,
            current_price=2800.0,
            timestamp=datetime.now()
        )
        position2.unrealized_pnl = -200.0
        
        self.portfolio.positions["BTC-USD"] = position1
        self.portfolio.positions["ETH-USD"] = position2
        
        total_unrealized = self.portfolio.get_unrealized_pnl()
        self.assertEqual(total_unrealized, 0.0)  # 200 - 200 = 0
    
    def test_export_and_save_data(self):
        """Testa exportação e salvamento de dados."""
        # Adicionar alguns dados
        from src.trading.strategies.base_strategy import Position
        
        position = Position(
            symbol="BTC-USD",
            side="buy",
            size=0.1,
            entry_price=50000.0,
            current_price=52000.0,
            timestamp=datetime.now()
        )
        
        self.portfolio.add_position(position)
        self.portfolio.close_position("BTC-USD", 52000.0, "profit", "test")
        
        # Exportar dados
        data = self.portfolio.export_data()
        
        self.assertIn("account_balance", data)
        self.assertIn("positions", data)
        self.assertIn("metrics", data)
        self.assertIn("trade_history", data)
        
        # Verificar estrutura
        self.assertEqual(len(data["trade_history"]), 1)
        self.assertEqual(data["trade_history"][0]["symbol"], "BTC-USD")
        self.assertEqual(data["trade_history"][0]["pnl"], 200.0)


class TestEndToEndIntegration(unittest.TestCase):
    """Testes de integração end-to-end."""
    
    def setUp(self):
        """Configuração inicial."""
        # Mock do cliente Coinbase
        self.mock_client = Mock(spec=CoinbaseClient)
        self.mock_client.test_connection.return_value = True
        
        # Mock de dados de mercado
        self.mock_client.get_product_ticker.return_value = {
            'price': '50000.0',
            'volume': '2000000'
        }
        
        # Mock de candles para análise técnica
        self.mock_candles = [
            {
                'start': str(int((datetime.now() - timedelta(minutes=i)).timestamp())),
                'open': str(50000 + i * 50),  # Tendência de alta
                'high': str(50100 + i * 50),
                'low': str(49900 + i * 50),
                'close': str(50050 + i * 50),
                'volume': str(1000000 + i * 1000)
            }
            for i in range(100)
        ]
        
        self.mock_client.get_product_candles.return_value = self.mock_candles
        
        self.trading_bot = TradingBot(self.mock_client)
    
    async def test_complete_trading_workflow(self):
        """Testa fluxo completo de trading."""
        # 1. Atualizar dados de mercado
        await self.trading_bot._update_market_data()
        
        # Verificar se dados foram carregados
        self.assertIn("BTC-USD", self.trading_bot.market_data_cache)
        
        # 2. Processar sinais
        await self.trading_bot._process_new_signals()
        
        # Verificar se sinais foram processados
        # (Pode não gerar ordens dependendo dos dados mock)
        
        # 3. Simular execução de ordem manualmente
        from src.trading.strategies.base_strategy import TradeOrder, OrderSide, OrderType
        
        order = TradeOrder(
            symbol="BTC-USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            size=0.1,
            metadata={"strategy": "swing_trading"}
        )
        
        self.trading_bot.pending_orders["test_order"] = order
        
        # 4. Executar ordens pendentes
        await self.trading_bot._execute_pending_orders()
        
        # Verificar se ordem foi executada
        self.assertEqual(len(self.trading_bot.pending_orders), 0)
        
        # 5. Verificar posição criada
        if "BTC-USD" in self.trading_bot.portfolio_manager.positions:
            position = self.trading_bot.portfolio_manager.positions["BTC-USD"]
            self.assertEqual(position.symbol, "BTC-USD")
            self.assertEqual(position.side, "buy")
            self.assertEqual(position.size, 0.1)
            
            # 6. Simular mudança de preço e verificar saída
            self.trading_bot.market_data_cache["BTC-USD"]["price"] = 55000.0
            await self.trading_bot._update_position_prices()
            
            # 7. Verificar condições de saída
            await self.trading_bot._check_position_exits()
    
    def test_bot_status_and_metrics(self):
        """Testa status e métricas dos bots."""
        # Status do bot de trading
        trading_status = self.trading_bot.get_status()
        
        self.assertIn("is_running", trading_status)
        self.assertIn("portfolio_status", trading_status)
        self.assertIn("strategies", trading_status)
        
        # Status do bot de sinais
        signal_status = self.trading_bot.signal_bot.get_status()
        
        self.assertIn("is_running", signal_status)
        self.assertIn("trading_pairs", signal_status)
        self.assertIn("performance_metrics", signal_status)
        
        # Resumo do portfólio
        portfolio_summary = self.trading_bot.get_portfolio_summary()
        
        self.assertIn("portfolio_metrics", portfolio_summary)
        self.assertIn("positions", portfolio_summary)
        self.assertIn("recent_trades", portfolio_summary)
    
    def test_error_handling(self):
        """Testa tratamento de erros."""
        # Simular erro na API
        self.mock_client.get_product_ticker.side_effect = Exception("API Error")
        
        # Deve lidar com erro graciosamente
        async def test_error():
            await self.trading_bot._update_market_data()
        
        # Não deve levantar exceção
        asyncio.run(test_error())
        
        # Verificar se métricas de erro foram atualizadas
        # (Implementação específica dependeria do logging)


if __name__ == '__main__':
    # Configurar logging para testes
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Executar testes
    unittest.main(verbosity=2)

