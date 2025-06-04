# Pesquisa API Coinbase - Fase 1

## SDK Python Oficial da Coinbase

### Visão Geral
- **Nome**: Advanced Trade Python SDK
- **Funcionalidade**: Facilita interação com a Coinbase Advanced Trade API
- **Recursos**: Autenticação, conexões HTTP, métodos auxiliares

### Componentes Principais
1. **REST API Client**: Interage com endpoints da Advanced Trade REST API
2. **WebSocket Client**: Interage com a WebSocket API para dados em tempo real

### Recursos Disponíveis
- **GitHub**: https://github.com/coinbase/coinbase-advanced-py
- **PyPI**: Disponível para instalação via pip
- **Documentação**: README e CHANGELOG disponíveis
- **Guias**: "Make Your First Trade" e "Listen for Order Updates"

### Informações Importantes
- Requer criação de API key (referência ao "Getting Started" guide)
- Suporte tanto para REST quanto WebSocket
- SDK oficial mantido pela Coinbase

## Próximos Passos
- Acessar repositório GitHub para detalhes técnicos
- Verificar documentação da API REST
- Analisar endpoints disponíveis
- Estudar autenticação e rate limiting



## SDK Python - Detalhes Técnicos

### Instalação
```bash
pip3 install coinbase-advanced-py
```

### Autenticação
- **Tipo**: Cloud Developer Platform (CDP) API Keys
- **Formato da chave**: `organizations/{org_id}/apiKeys/{key_id}`
- **Chave privada**: Formato EC PRIVATE KEY
- **Métodos de configuração**:
  - Variáveis de ambiente (COINBASE_API_KEY, COINBASE_API_SECRET)
  - Parâmetros diretos no código
  - Arquivo JSON baixado após criação da chave
  - Objeto file-like

### REST API Client

#### Configuração Básica
```python
from coinbase.rest import RESTClient

# Usando variáveis de ambiente
client = RESTClient()

# Usando parâmetros diretos
client = RESTClient(api_key=api_key, api_secret=api_secret)

# Usando arquivo JSON
client = RESTClient(key_file="path/to/cdp_api_key.json")

# Com timeout personalizado
client = RESTClient(api_key=api_key, api_secret=api_secret, timeout=5)
```

#### Funcionalidades Principais
- **Contas**: `client.get_accounts()`
- **Ordens**: `client.market_order_buy(client_order_id, product_id, quote_size)`
- **Produtos**: `client.get_product(product_id)`
- **Dados de mercado**: `client.get_market_trades(product_id, limit)`
- **Portfólios**: `client.create_portfolio(name)`

#### Recursos Avançados
- Objetos de resposta customizados com dot-notation
- Suporte a kwargs para parâmetros adicionais
- Métodos genéricos REST (get, post, put, delete)
- Headers de rate limit opcionais

### WebSocket API Client

#### Configuração
```python
from coinbase.websocket import WSClient

def on_message(msg):
    print(msg)

client = WSClient(api_key=api_key, api_secret=api_secret, on_message=on_message)
```

#### Funcionalidades
- **Callback obrigatório**: `on_message` para processar mensagens
- **Callbacks opcionais**: `on_open`, `on_close`
- **Configurações**: timeout, max_size para mensagens
- **Canais disponíveis**: market data, user data, futures

#### WebSocket User API Client
```python
from coinbase.websocket import WSUserClient

client = WSUserClient(api_key=api_key, api_secret=api_secret, on_message=on_message)
```
- **Canais especializados**: user channel, futures_balance_summary channel

### Rate Limiting
- Headers informativos disponíveis na resposta
- Configuração: `rate_limit_headers=True` no RESTClient
- Headers anexados como campos no corpo da resposta

### Segurança
- **Aviso**: Não salvar secrets diretamente no código
- **Recomendação**: Usar secrets manager
- **Cuidado**: Evitar exposição pública de chaves

## Próximos Passos de Pesquisa
- Verificar documentação oficial da API REST
- Analisar endpoints específicos para trading
- Estudar canais WebSocket disponíveis
- Verificar limites de rate e sandbox


## Endpoints da Advanced Trade API

### URL Base
`https://api.coinbase.com/api/v3/brokerage/{resource}`

### Endpoints Principais

#### Contas e Autenticação
- **List Accounts**: `GET /accounts` (permissão: view)
- **Get Account**: `GET /accounts/:account_id` (permissão: view)

#### Ordens e Trading
- **Create Order**: `POST /orders` (permissão: trade)
- **Cancel Orders**: `POST /orders/batch_cancel` (permissão: trade)
- **List Orders**: `GET /orders/historical/batch` (permissão: view)
- **Get Order**: `GET /orders/historical/{order_id}` (permissão: view)
- **List Fills**: `GET /orders/historical/fills` (permissão: view)
- **Preview Orders**: `POST /orders/preview` (permissão: view)

#### Dados de Mercado
- **Get Best Bid/Ask**: `GET /best_bid_ask` (permissão: view)
- **Get Product Book**: `GET /product_book` (permissão: view)
- **List Products**: `GET /products` (permissão: view)
- **Get Product**: `GET /products/{product_id}` (permissão: view)
- **Get Product Candles**: `GET /products/{product_id}/candles` (permissão: view)
- **Get Market Trades**: `GET /products/{product_id}/ticker` (permissão: view)

#### Portfólios
- **List Portfolios**: `GET /portfolios` (permissão: view)
- **Create Portfolio**: `POST /portfolios` (permissão: view)
- **Move Portfolio Funds**: `POST /portfolios` (permissão: transfer)
- **Get Portfolio Breakdown**: `GET /portfolios` (permissão: view)
- **Delete Portfolio**: `DELETE /portfolios` (permissão: trade)
- **Edit Portfolio**: `PUT /portfolios` (permissão: trade)

#### Conversões
- **Create Convert Quote**: `POST /convert/quote` (permissão: trade)
- **Commit Convert Trade**: `POST /convert/{trade_id}` (permissão: trade)
- **Get Convert Trade**: `GET /convert/{trade_id}` (permissão: view)

#### Futuros
- **Get Futures Balance Summary**: `GET /cfm/balance_summary` (permissão: view)
- **List Futures Positions**: `GET /cfm/positions` (permissão: view)
- **Get Futures Position**: `GET /cfm/positions/{product_id}` (permissão: view)

## Rate Limiting

### Limites Gerais
- **Limite padrão**: 10.000 requests por hora por API key
- **Código de erro**: 429 (rate_limit_exceeded)
- **Endpoints públicos**: 10 requests por segundo por IP (throttling coletivo)

### Advanced Trade API - Limites Específicos
- **Endpoints privados**: 30 requests por segundo (RPS) por portfólio
- **Disponível apenas**: Para usuários com CDP API keys
- **Throttling inconsistente**: Pode ocorrer ocasionalmente

### Headers de Resposta
- **X-ratelimit-limit**: Limite atual para este endpoint
- **X-ratelimit-remaining**: Número de requests restantes na janela atual
- **X-ratelimit-reset**: Tempo em segundos para reset da janela

### Exemplos de Rate Limit
1. **Global**: 30 RPS para todos os endpoints
2. **Específico**: 10 RPS para order management + 30 RPS para outros

## Permissões de API Key
- **view**: Visualizar dados (contas, ordens, mercado)
- **trade**: Executar trades e gerenciar ordens
- **transfer**: Mover fundos entre portfólios

## Próximos Passos
- Verificar ambiente sandbox
- Analisar canais WebSocket disponíveis
- Estudar estrutura de dados das respostas
- Verificar documentação de autenticação CDP


## Ambiente Sandbox

### URL do Sandbox
`https://api-sandbox.coinbase.com/api/v3/brokerage/{resource}`

### Características
- **Sem autenticação**: Requests podem ser feitos sem API keys
- **Respostas estáticas**: Todas as respostas são pré-definidas e mockadas
- **Formato idêntico**: Mesmo formato das respostas de produção
- **Header customizado**: `X-Sandbox:` para triggerar variações pré-definidas

### Endpoints Disponíveis no Sandbox
- **Contas**: List Accounts, Get Account
- **Ordens**: Create Order, Cancel Orders, Edit Order, List Orders, Get Order, Preview Order, Close Position
- **Portfólios**: List Portfolios, Allocate Portfolio
- **Perpétuos**: Portfolio Summary, Positions, Balances
- **Multi Asset Collateral**: Opt In/Out

### Limitações
- Apenas endpoints de Accounts e Orders disponíveis
- Respostas mockadas (não refletem dados reais)
- Funcionalidade limitada comparada à produção

## Resumo da Pesquisa

### Pontos Fortes da API
1. **SDK oficial Python** bem documentado e mantido
2. **WebSocket** para dados em tempo real
3. **Rate limiting** adequado para bots (30 RPS)
4. **Sandbox** para testes seguros
5. **Documentação completa** e exemplos

### Considerações para os Bots
1. **Bot de Sinais**: Usar WebSocket para dados em tempo real + REST para dados históricos
2. **Bot de Trading**: Usar REST API para execução de ordens + WebSocket para monitoramento
3. **Rate Limiting**: Implementar controle de requests (30 RPS máximo)
4. **Autenticação**: CDP API Keys com permissões adequadas
5. **Testes**: Usar sandbox antes de produção

### Próximas Etapas
- Definir arquitetura modular
- Implementar cliente base da API
- Desenvolver sistema de sinais
- Criar bot de trading
- Containerizar com Docker

