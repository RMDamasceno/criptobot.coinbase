# 🐳 Docker Setup - Crypto Bots

Este guia explica como executar os bots de criptomoedas usando Docker.

## 📋 Pré-requisitos

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM disponível
- 10GB espaço em disco

## 🚀 Início Rápido

### 1. Configuração Inicial

```bash
# Clonar o repositório
git clone <repository-url>
cd crypto-bots

# Copiar arquivo de configuração
cp .env.example .env

# Editar configurações (OBRIGATÓRIO)
nano .env
```

### 2. Configurar Credenciais

Edite o arquivo `.env` com suas credenciais da Coinbase:

```env
# API Coinbase
COINBASE_API_KEY=sua_api_key_aqui
COINBASE_API_SECRET=sua_api_secret_aqui
COINBASE_ENVIRONMENT=sandbox  # ou 'production'

# Configurações dos Bots
DRY_RUN_MODE=true
TRADING_PAIRS=BTC-USD,ETH-USD
INITIAL_BALANCE=10000.0
```

### 3. Executar os Bots

#### Modo Simples (Recomendado para iniciantes)
```bash
# Usar script de gerenciamento
./docker-manager.sh start simple

# Ou diretamente com docker-compose
docker-compose -f docker-compose.simple.yml up -d
```

#### Modo Completo (Com monitoramento)
```bash
./docker-manager.sh start monitoring
```

## 🛠️ Script de Gerenciamento

O script `docker-manager.sh` facilita o gerenciamento dos containers:

```bash
# Construir imagens
./docker-manager.sh build

# Iniciar serviços
./docker-manager.sh start simple      # Apenas bots
./docker-manager.sh start monitoring  # Com Prometheus/Grafana
./docker-manager.sh start web        # Com interface web

# Verificar status
./docker-manager.sh status

# Ver logs
./docker-manager.sh logs              # Todos os logs
./docker-manager.sh logs signal-bot   # Logs específicos
./docker-manager.sh logs trading-bot -f  # Seguir logs

# Parar serviços
./docker-manager.sh stop

# Reiniciar
./docker-manager.sh restart simple

# Limpeza
./docker-manager.sh cleanup

# Backup
./docker-manager.sh backup

# Verificar saúde
./docker-manager.sh health
```

## 📊 Monitoramento

### Grafana Dashboard
- URL: http://localhost:3000
- Usuário: admin
- Senha: admin123 (configurável via GRAFANA_PASSWORD)

### Prometheus Metrics
- URL: http://localhost:9090

### Logs
```bash
# Ver logs em tempo real
./docker-manager.sh logs -f

# Logs específicos
./docker-manager.sh logs signal-bot
./docker-manager.sh logs trading-bot
```

## 🔧 Comandos Úteis

### Executar Comandos nos Containers
```bash
# Abrir shell no bot de sinais
./docker-manager.sh exec signal-bot bash

# Executar análise única
./docker-manager.sh exec signal-bot python bots/signal_bot_runner.py --analyze BTC-USD

# Ver status do bot de trading
./docker-manager.sh exec trading-bot python bots/trading_bot_runner.py --status
```

### Verificar Recursos
```bash
# Status dos containers
docker-compose ps

# Uso de recursos
docker stats

# Logs do sistema
docker-compose logs
```

## 📁 Estrutura de Volumes

```
crypto-bots/
├── logs/          # Logs dos bots (montado no container)
├── data/          # Dados persistentes (montado no container)
├── config/        # Configurações adicionais
└── backups/       # Backups automáticos
```

## 🔒 Segurança

### Variáveis de Ambiente Sensíveis
- Nunca commite o arquivo `.env` com credenciais reais
- Use secrets do Docker Swarm em produção
- Considere usar um gerenciador de secrets

### Rede
- Os containers usam uma rede isolada
- Apenas portas necessárias são expostas
- Redis protegido por senha

## 🚨 Troubleshooting

### Container não inicia
```bash
# Verificar logs
./docker-manager.sh logs

# Verificar saúde
./docker-manager.sh health

# Reconstruir imagem
./docker-manager.sh build
```

### Problemas de Conectividade
```bash
# Testar conexão com API
./docker-manager.sh exec signal-bot python -c "
from src.core.coinbase_client import CoinbaseClient
client = CoinbaseClient()
print('Conexão:', 'OK' if client.test_connection() else 'FALHOU')
"
```

### Limpeza Completa
```bash
# Parar tudo e limpar
./docker-manager.sh cleanup

# Remover volumes (CUIDADO: perde dados)
docker-compose down -v
docker volume prune -f
```

## 📈 Produção

### Configurações Recomendadas

1. **Desabilitar modo dry-run**:
   ```env
   DRY_RUN_MODE=false
   ```

2. **Usar ambiente de produção**:
   ```env
   COINBASE_ENVIRONMENT=production
   ```

3. **Configurar limites de recursos**:
   ```yaml
   # No docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '0.5'
   ```

4. **Backup automático**:
   ```bash
   # Cron job para backup diário
   0 2 * * * cd /path/to/crypto-bots && ./docker-manager.sh backup
   ```

### Monitoramento em Produção

1. **Alertas**: Configure alertas no Grafana
2. **Logs**: Use um agregador de logs (ELK Stack)
3. **Métricas**: Monitore CPU, memória e rede
4. **Uptime**: Configure health checks

## 🔄 Atualizações

```bash
# Atualizar código e reiniciar
git pull
./docker-manager.sh update simple

# Atualizar apenas imagens
./docker-manager.sh build
./docker-manager.sh restart
```

## 📞 Suporte

- Logs detalhados: `./docker-manager.sh logs -f`
- Status de saúde: `./docker-manager.sh health`
- Documentação: Consulte o README.md principal

