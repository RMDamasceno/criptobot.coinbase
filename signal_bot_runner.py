#!/usr/bin/env python3
"""
Runner para o Bot de Sinais.

Este script é o ponto de entrada para executar o bot de sinais.
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
from src.signals.signal_bot import SignalBot

logger = get_logger(__name__)


async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Bot de Sinais de Criptomoedas")
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
        "--interval",
        type=int,
        help="Intervalo de atualização em segundos"
    )
    parser.add_argument(
        "--analyze",
        type=str,
        help="Analisar um único par e sair"
    )
    
    args = parser.parse_args()
    
    # Carregar configurações
    if args.config:
        os.environ["ENV_FILE"] = args.config
    
    settings = get_settings()
    
    # Sobrescrever configurações com argumentos da linha de comando
    if args.pairs:
        settings.trading_pairs_str = args.pairs
    
    if args.interval:
        settings.signal_update_interval = args.interval
    
    # Inicializar cliente e bot
    client = CoinbaseClient()
    signal_bot = SignalBot(client)
    
    # Modo de análise única
    if args.analyze:
        symbol = args.analyze
        print(f"Analisando par: {symbol}")
        
        result = await signal_bot.analyze_single_symbol(symbol)
        
        if result:
            print("\n=== RESULTADO DA ANÁLISE ===")
            if "error" in result:
                print(f"ERRO: {result['error']}")
            elif result["analysis"]:
                analysis = result["analysis"]
                print(f"Símbolo: {symbol}")
                print(f"Sinal: {analysis.get('sinal', 'N/A').upper()}")
                print(f"Confiança: {analysis.get('confianca', {}).get('valor', 0)}%")
                print(f"Tendência: {analysis.get('tendencia', {}).get('direcao', 'N/A')}")
                print(f"Força da tendência: {analysis.get('tendencia', {}).get('forca', {}).get('valor', 0)}%")
                
                if "indicadores" in analysis:
                    print("\nIndicadores:")
                    for name, value in analysis["indicadores"].items():
                        print(f"- {name}: {value}")
            else:
                print("Nenhum sinal gerado (dados insuficientes ou abaixo do threshold)")
        else:
            print("Falha ao analisar o par")
        
        return
    
    # Modo normal (loop contínuo)
    print(f"Iniciando Bot de Sinais")
    print(f"Pares monitorados: {', '.join(settings.trading_pairs)}")
    print(f"Intervalo de atualização: {settings.signal_update_interval}s")
    print(f"Pressione Ctrl+C para encerrar")
    
    try:
        await signal_bot.start()
    except KeyboardInterrupt:
        print("\nEncerrando bot...")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        print(f"\nErro fatal: {e}")
    finally:
        await signal_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot encerrado pelo usuário")
    except Exception as e:
        print(f"Erro não tratado: {e}")
        sys.exit(1)

