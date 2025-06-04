#!/bin/bash

# Script de gerenciamento Docker para os Bots de Criptomoedas
# Uso: ./docker-manager.sh [comando] [opções]

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
PROJECT_NAME="crypto-bots"
COMPOSE_FILE="docker-compose.yml"
SIMPLE_COMPOSE_FILE="docker-compose.simple.yml"

# Funções auxiliares
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se Docker está instalado
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker não está instalado!"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose não está instalado!"
        exit 1
    fi
}

# Verificar se arquivo .env existe
check_env_file() {
    if [ ! -f ".env" ]; then
        log_warning "Arquivo .env não encontrado. Copiando de .env.example..."
        cp .env.example .env
        log_info "Configure o arquivo .env com suas credenciais antes de continuar."
        exit 1
    fi
}

# Construir imagens
build() {
    log_info "Construindo imagens Docker..."
    docker-compose -f $COMPOSE_FILE build --no-cache
    log_success "Imagens construídas com sucesso!"
}

# Iniciar serviços
start() {
    local mode=${1:-"simple"}
    
    check_env_file
    
    if [ "$mode" = "simple" ]; then
        log_info "Iniciando bots em modo simples..."
        docker-compose -f $SIMPLE_COMPOSE_FILE up -d
    elif [ "$mode" = "full" ]; then
        log_info "Iniciando todos os serviços..."
        docker-compose -f $COMPOSE_FILE up -d
    elif [ "$mode" = "monitoring" ]; then
        log_info "Iniciando com monitoramento..."
        docker-compose -f $COMPOSE_FILE --profile monitoring up -d
    elif [ "$mode" = "web" ]; then
        log_info "Iniciando com interface web..."
        docker-compose -f $COMPOSE_FILE --profile web --profile monitoring up -d
    else
        log_error "Modo inválido: $mode"
        log_info "Modos disponíveis: simple, full, monitoring, web"
        exit 1
    fi
    
    log_success "Serviços iniciados!"
    show_status
}

# Parar serviços
stop() {
    log_info "Parando serviços..."
    docker-compose -f $COMPOSE_FILE down
    docker-compose -f $SIMPLE_COMPOSE_FILE down 2>/dev/null || true
    log_success "Serviços parados!"
}

# Reiniciar serviços
restart() {
    local mode=${1:-"simple"}
    log_info "Reiniciando serviços..."
    stop
    sleep 2
    start $mode
}

# Mostrar logs
logs() {
    local service=${1:-""}
    local follow=${2:-""}
    
    if [ -n "$service" ]; then
        if [ "$follow" = "-f" ] || [ "$follow" = "--follow" ]; then
            docker-compose -f $COMPOSE_FILE logs -f $service
        else
            docker-compose -f $COMPOSE_FILE logs --tail=100 $service
        fi
    else
        if [ "$follow" = "-f" ] || [ "$follow" = "--follow" ]; then
            docker-compose -f $COMPOSE_FILE logs -f
        else
            docker-compose -f $COMPOSE_FILE logs --tail=100
        fi
    fi
}

# Mostrar status
show_status() {
    log_info "Status dos serviços:"
    docker-compose -f $COMPOSE_FILE ps
    echo
    
    log_info "Uso de recursos:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker-compose -f $COMPOSE_FILE ps -q) 2>/dev/null || true
}

# Executar comando em container
exec_command() {
    local service=${1:-"signal-bot"}
    local command=${2:-"bash"}
    
    log_info "Executando comando no serviço $service..."
    docker-compose -f $COMPOSE_FILE exec $service $command
}

# Limpar recursos
cleanup() {
    log_info "Limpando recursos Docker..."
    
    # Parar e remover containers
    docker-compose -f $COMPOSE_FILE down -v --remove-orphans
    docker-compose -f $SIMPLE_COMPOSE_FILE down -v --remove-orphans 2>/dev/null || true
    
    # Remover imagens não utilizadas
    docker image prune -f
    
    # Remover volumes órfãos
    docker volume prune -f
    
    log_success "Limpeza concluída!"
}

# Backup de dados
backup() {
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    
    log_info "Criando backup em $backup_dir..."
    mkdir -p $backup_dir
    
    # Backup de logs
    if [ -d "logs" ]; then
        cp -r logs $backup_dir/
    fi
    
    # Backup de dados
    if [ -d "data" ]; then
        cp -r data $backup_dir/
    fi
    
    # Backup de configurações
    cp .env $backup_dir/ 2>/dev/null || true
    cp docker-compose*.yml $backup_dir/
    
    log_success "Backup criado em $backup_dir"
}

# Atualizar imagens
update() {
    log_info "Atualizando imagens..."
    
    # Fazer backup antes da atualização
    backup
    
    # Parar serviços
    stop
    
    # Reconstruir imagens
    build
    
    # Reiniciar serviços
    start ${1:-"simple"}
    
    log_success "Atualização concluída!"
}

# Monitoramento de saúde
health_check() {
    log_info "Verificando saúde dos serviços..."
    
    local healthy=0
    local total=0
    
    for container in $(docker-compose -f $COMPOSE_FILE ps -q); do
        total=$((total + 1))
        health=$(docker inspect --format='{{.State.Health.Status}}' $container 2>/dev/null || echo "no-health-check")
        name=$(docker inspect --format='{{.Name}}' $container | sed 's/\///')
        
        if [ "$health" = "healthy" ] || [ "$health" = "no-health-check" ]; then
            echo -e "${GREEN}✓${NC} $name: $health"
            healthy=$((healthy + 1))
        else
            echo -e "${RED}✗${NC} $name: $health"
        fi
    done
    
    echo
    log_info "Serviços saudáveis: $healthy/$total"
    
    if [ $healthy -eq $total ]; then
        log_success "Todos os serviços estão funcionando!"
    else
        log_warning "Alguns serviços podem estar com problemas."
    fi
}

# Mostrar ajuda
show_help() {
    echo "Script de gerenciamento Docker para Crypto Bots"
    echo
    echo "Uso: $0 [comando] [opções]"
    echo
    echo "Comandos:"
    echo "  build                    Construir imagens Docker"
    echo "  start [mode]            Iniciar serviços (modes: simple, full, monitoring, web)"
    echo "  stop                    Parar todos os serviços"
    echo "  restart [mode]          Reiniciar serviços"
    echo "  logs [service] [-f]     Mostrar logs (use -f para seguir)"
    echo "  status                  Mostrar status dos serviços"
    echo "  exec [service] [cmd]    Executar comando em container"
    echo "  cleanup                 Limpar recursos Docker"
    echo "  backup                  Fazer backup dos dados"
    echo "  update [mode]           Atualizar e reiniciar serviços"
    echo "  health                  Verificar saúde dos serviços"
    echo "  help                    Mostrar esta ajuda"
    echo
    echo "Exemplos:"
    echo "  $0 start simple         # Iniciar apenas os bots"
    echo "  $0 start monitoring     # Iniciar com Prometheus/Grafana"
    echo "  $0 logs signal-bot -f   # Seguir logs do bot de sinais"
    echo "  $0 exec trading-bot bash # Abrir shell no bot de trading"
}

# Função principal
main() {
    check_docker
    
    case "${1:-help}" in
        build)
            build
            ;;
        start)
            start ${2:-"simple"}
            ;;
        stop)
            stop
            ;;
        restart)
            restart ${2:-"simple"}
            ;;
        logs)
            logs $2 $3
            ;;
        status)
            show_status
            ;;
        exec)
            exec_command $2 "${@:3}"
            ;;
        cleanup)
            cleanup
            ;;
        backup)
            backup
            ;;
        update)
            update ${2:-"simple"}
            ;;
        health)
            health_check
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Comando inválido: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Executar função principal
main "$@"

