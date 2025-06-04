#!/usr/bin/env python3
"""
Runner para o Bot de Trading.

Este script é o ponto de entrada para executar o bot de trading.
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path

# Adicionar diretório raiz ao path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from src.config.settings import get_settings
from src.config.logging_config import get_logger, configure_logging
from src.core.coinbase_client import CoinbaseClient
from src.trading.trading_bot import TradingBot

logger = get_logger(__name__)


async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Bot de Trading de Criptomoedas")
    parser.add_argument(
        "--config",
        type=str,
        help="Caminho para arquivo de configuração .env"
    )
    parser.add_argument(
        "--pairs",
        type=str,
        help="Lista de pares de trading separados por vírgula (ex: BTC-USD,ETH-USD)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executar em modo simulação (sem trades reais)"
    )
    parser.add_argument(
        "--balance",
        type=float,
        help="Saldo inicial para simulação"
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Intervalo de atualização em segundos"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar status do bot e sair"
    )
    parser.add_argument(
        "--portfolio",
        action="store_true",
        help="Mostrar resumo do portfólio e sair"
    )
    
    args = parser.parse_args()
    
    # Carregar configurações
    if args.config:
        os.environ["ENV_FILE"] = args.config
    
    settings = get_settings()
    
    # Sobrescrever configurações com argumentos da linha de comando
    if args.pairs:
        settings.trading_pairs_str = args.pairs
    
    if args.dry_run:
        settings.dry_run_mode = True
    
    if args.balance:
        settings.initial_balance = args.balance
    
    if args.interval:
        settings.trading_update_interval = args.interval
    
    # Inicializar cliente e bot
    client = CoinbaseClient()
    trading_bot = TradingBot(client)
    
    # Modo status
    if args.status:
        print("=== STATUS DO BOT DE TRADING ===")
        status = trading_bot.get_status()
        
        print(f"Status: {'Executando' if status['is_running'] else 'Parado'}")
        print(f"Modo: {'Simulação' if status['dry_run'] else 'Real'}")
        print(f"Pares monitorados: {', '.join(status['trading_pairs'])}")
        print(f"Uptime: {status['uptime']}")
        print(f"Trades executados: {status['performance_metrics']['trades_executed']}")
        print(f"Ordens pendentes: {status['pending_orders']}")
        
        portfolio = status['portfolio_status']
        print(f"\n=== PORTFÓLIO ===")
        print(f"Saldo total: ${portfolio['account_balance']:,.2f}")
        print(f"Valor do portfólio: ${portfolio['total_portfolio_value']:,.2f}")
        print(f"P&L não realizado: ${portfolio['unrealized_pnl']:,.2f}")
        print(f"P&L realizado: ${portfolio['realized_pnl']:,.2f}")
        print(f"Posições abertas: {portfolio['open_positions']}")
        print(f"Total de trades: {portfolio['total_trades']}")
        print(f"Taxa de vitória: {portfolio['win_rate']:.1f}%")
        
        return
    
    # Modo portfólio
    if args.portfolio:
        print("=== RESUMO DO PORTFÓLIO ===")
        summary = trading_bot.get_portfolio_summary()
        
        metrics = summary['portfolio_metrics']
        print(f"Valor total: ${metrics['total_value']:,.2f}")
        print(f"P&L total: ${metrics['total_pnl']:,.2f}")
        print(f"P&L diário: ${metrics['daily_pnl']:,.2f}")
        print(f"Drawdown máximo: {metrics['max_drawdown']:.2f}%")
        print(f"Fator de lucro: {metrics['profit_factor']:.2f}")
        print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        
        positions = summary['positions']
        if positions:
            print(f"\n=== POSIÇÕES ABERTAS ({len(positions)}) ===")
            for symbol, pos in positions.items():
                pnl_pct = pos['unrealized_pnl_pct']
                pnl_color = "🟢" if pnl_pct > 0 else "🔴" if pnl_pct < 0 else "⚪"
                print(f"{pnl_color} {symbol}: {pos['side'].upper()} ${pos['size']:.4f} @ ${pos['entry_price']:.2f} "
                      f"(atual: ${pos['current_price']:.2f}, P&L: {pnl_pct:+.2f}%)")
        
        trades = summary['recent_trades']
        if trades:
            print(f"\n=== TRADES RECENTES ({len(trades)}) ===")
            for trade in trades[-5:]:  # Últimos 5 trades
                pnl_color = "🟢" if trade['pnl'] > 0 else "🔴"
                print(f"{pnl_color} {trade['symbol']}: {trade['side'].upper()} "
                      f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} "
                      f"(P&L: {trade['pnl_pct']:+.2f}%)")
        
        return
    
    # Modo normal (execução do bot)
    print(f"🤖 Iniciando Bot de Trading")
    print(f"Modo: {'🔄 Simulação' if settings.dry_run_mode else '💰 Real'}")
    print(f"Pares monitorados: {', '.join(settings.trading_pairs)}")
    print(f"Saldo inicial: ${settings.initial_balance:,.2f}")
    print(f"Intervalo de atualização: {settings.trading_update_interval}s")
    print(f"Máximo de posições: {settings.max_positions}")
    print(f"Risco por trade: {settings.risk_percentage}%")
    
    if settings.dry_run_mode:
        print("\n⚠️  MODO SIMULAÇÃO ATIVO - Nenhum trade real será executado")
    
    print(f"\nPressione Ctrl+C para encerrar")
    
    try:
        await trading_bot.start()
    except KeyboardInterrupt:
        print("\n🛑 Encerrando bot...")
        
        # Mostrar resumo final
        summary = trading_bot.get_portfolio_summary()
        metrics = summary['portfolio_metrics']
        
        print(f"\n=== RESUMO FINAL ===")
        print(f"Valor final: ${metrics['total_value']:,.2f}")
        print(f"P&L total: ${metrics['total_pnl']:,.2f}")
        print(f"Total de trades: {metrics['total_trades']}")
        print(f"Taxa de vitória: {metrics['win_rate']:.1f}%")
        
        if summary['positions']:
            print(f"⚠️  {len(summary['positions'])} posições ainda abertas")
            
            # Perguntar se deve fechar posições
            try:
                response = input("Deseja fechar todas as posições? (s/N): ")
                if response.lower() in ['s', 'sim', 'y', 'yes']:
                    print("Fechando todas as posições...")
                    await trading_bot.force_close_all_positions()
                    print("✅ Todas as posições foram fechadas")
            except:
                pass
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        print(f"\n❌ Erro fatal: {e}")
    finally:
        await trading_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot encerrado pelo usuário")
    except Exception as e:
        print(f"Erro não tratado: {e}")
        sys.exit(1)

