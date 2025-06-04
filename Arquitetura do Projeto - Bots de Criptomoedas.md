# Arquitetura do Projeto - Bots de Criptomoedas

## Visão Geral

O projeto será estruturado de forma modular, com dois bots principais que compartilham componentes comuns. A arquitetura seguirá princípios de separação de responsabilidades e reutilização de código.

## Estrutura de Diretórios

```
crypto-bots/
├── README.md
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── logging_config.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── coinbase_client.py
│   │   ├── websocket_client.py
│   │   ├── rate_limiter.py
│   │   └── exceptions.py
│   │
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── signal_bot.py
│   │   ├── indicators/
│   │   │   ├── __init__.py
│   │   │   ├── technical_indicators.py
│   │   │   ├── moving_averages.py
│   │   │   ├── rsi.py
│   │   │   ├── macd.py
│   │   │   └── bollinger_bands.py
│   │   ├── analyzers/
│   │   │   ├── __init__.py
│   │   │   ├── trend_analyzer.py
│   │   │   ├── volume_analyzer.py
│   │   │   └── pattern_analyzer.py
│   │   └── notifiers/
│   │       ├── __init__.py
│   │       ├── console_notifier.py
│   │       ├── file_notifier.py
│   │       └── webhook_notifier.py
│   │
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── trading_bot.py
│   │   ├── strategies/
│   │   │   ├── __init__.py
│   │   │   ├── base_strategy.py
│   │   │   ├── scalping_strategy.py
│   │   │   ├── swing_strategy.py
│   │   │   └── dca_strategy.py
│   │   ├── risk_management/
│   │   │   ├── __init__.py
│   │   │   ├── position_sizer.py
│   │   │   ├── stop_loss.py
│   │   │   └── take_profit.py
│   │   └── portfolio/
│   │       ├── __init__.py
│   │       ├── portfolio_manager.py
│   │       └── balance_tracker.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── market_data.py
│   │   ├── historical_data.py
│   │   ├── real_time_data.py
│   │   └── data_storage.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py
│       ├── validators.py
│       └── formatters.py
│
├── bots/
│   ├── signal_bot_runner.py
│   ├── trading_bot_runner.py
│   └── combined_bot_runner.py
│
├── tests/
│   ├── __init__.py
│   ├── test_core/
│   ├── test_signals/
│   ├── test_trading/
│   └── test_data/
│
├── docs/
│   ├── installation.md
│   ├── configuration.md
│   ├── usage.md
│   └── api_reference.md
│
├── scripts/
│   ├── setup.sh
│   ├── run_tests.sh
│   └── deploy.sh
│
├── data/
│   ├── logs/
│   ├── backtest/
│   └── signals/
│
└── docker/
    ├── Dockerfile.signals
    ├── Dockerfile.trading
    └── Dockerfile.combined
```

## Componentes Principais

### 1. Core (src/core/)
Componentes fundamentais compartilhados entre os bots:

- **coinbase_client.py**: Cliente REST da API Coinbase
- **websocket_client.py**: Cliente WebSocket para dados em tempo real
- **rate_limiter.py**: Controle de rate limiting
- **exceptions.py**: Exceções customizadas

### 2. Signals (src/signals/)
Bot de sinais de trading:

- **signal_bot.py**: Classe principal do bot de sinais
- **indicators/**: Indicadores técnicos (RSI, MACD, Bollinger Bands, etc.)
- **analyzers/**: Analisadores de tendência, volume e padrões
- **notifiers/**: Sistema de notificações (console, arquivo, webhook)

### 3. Trading (src/trading/)
Bot de negociações automáticas:

- **trading_bot.py**: Classe principal do bot de trading
- **strategies/**: Estratégias de trading (scalping, swing, DCA)
- **risk_management/**: Gestão de risco (stop-loss, take-profit)
- **portfolio/**: Gerenciamento de portfólio e balanços

### 4. Data (src/data/)
Gerenciamento de dados:

- **market_data.py**: Interface para dados de mercado
- **historical_data.py**: Dados históricos
- **real_time_data.py**: Dados em tempo real
- **data_storage.py**: Armazenamento e cache de dados

### 5. Configuration (src/config/)
Configurações do sistema:

- **settings.py**: Configurações gerais
- **logging_config.py**: Configuração de logs

## Arquitetura de Comunicação

### Bot de Sinais
```
WebSocket (Real-time) → Indicators → Analyzers → Notifiers
REST API (Historical) → Indicators → Analyzers → Notifiers
```

### Bot de Trading
```
Signals → Strategies → Risk Management → Portfolio → Orders (REST API)
WebSocket → Position Monitoring → Risk Management
```

### Fluxo de Dados
1. **Coleta**: WebSocket + REST API → Market Data
2. **Processamento**: Indicators → Technical Analysis
3. **Decisão**: Analyzers → Signal Generation
4. **Ação**: 
   - Bot de Sinais: Notifiers → Alerts
   - Bot de Trading: Strategies → Orders

## Padrões de Design

### 1. Strategy Pattern
- Estratégias de trading intercambiáveis
- Indicadores técnicos modulares
- Notificadores plugáveis

### 2. Observer Pattern
- Notificações de sinais
- Monitoramento de posições
- Eventos de mercado

### 3. Factory Pattern
- Criação de indicadores
- Instanciação de estratégias
- Configuração de clientes

### 4. Singleton Pattern
- Cliente da API Coinbase
- Configurações globais
- Rate limiter

## Configuração e Deployment

### Variáveis de Ambiente
```env
# API Coinbase
COINBASE_API_KEY=organizations/{org_id}/apiKeys/{key_id}
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----...
COINBASE_SANDBOX=true/false

# Bot Configuration
BOT_MODE=signals/trading/combined
LOG_LEVEL=INFO
DATA_STORAGE_PATH=/data

# Trading Configuration
DEFAULT_PORTFOLIO=default
RISK_PERCENTAGE=2.0
MAX_POSITIONS=5

# Notification Configuration
WEBHOOK_URL=https://hooks.slack.com/...
NOTIFICATION_LEVEL=all/important/critical
```

### Docker Containers
1. **signals-bot**: Container para bot de sinais
2. **trading-bot**: Container para bot de trading
3. **combined-bot**: Container com ambos os bots
4. **data-volume**: Volume persistente para dados

## Próximos Passos

1. Implementar estrutura base do projeto
2. Desenvolver cliente da API Coinbase
3. Criar sistema de indicadores técnicos
4. Implementar bot de sinais
5. Desenvolver bot de trading
6. Configurar containerização
7. Criar testes e documentação

