#!/usr/bin/env bash
# =============================================================================
# Platform Management Script
# Usage: ./scripts/manage.sh [command]
# =============================================================================
set -euo pipefail

COMPOSE="docker-compose -f docker/docker-compose.yml"
PYTHON="python -m src.cli"

case "${1:-help}" in

  start)
    echo "Starting all services..."
    $COMPOSE up -d
    echo "Dashboard: http://localhost:8501"
    ;;

  stop)
    echo "Stopping all services..."
    $COMPOSE down
    ;;

  restart)
    $COMPOSE restart
    ;;

  logs)
    service="${2:-}"
    if [ -n "$service" ]; then
      $COMPOSE logs -f "$service"
    else
      $COMPOSE logs -f
    fi
    ;;

  scan)
    echo "Running manual scan..."
    $COMPOSE exec scheduler $PYTHON scan
    ;;

  scan-equities)
    $COMPOSE exec scheduler $PYTHON scan --equities
    ;;

  scan-commodities)
    $COMPOSE exec scheduler $PYTHON scan --commodities
    ;;

  scan-agriculture)
    $COMPOSE exec scheduler $PYTHON scan --agriculture
    ;;

  init-db)
    echo "Initialising database..."
    $COMPOSE exec scheduler $PYTHON init-db
    ;;

  test)
    echo "Running test suite..."
    docker build -t swing-test -f docker/Dockerfile .
    docker run --rm \
      -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
      -e TELEGRAM_BOT_TOKEN="" \
      -e FRED_API_KEY="" \
      swing-test \
      pytest tests/ -v --tb=short
    ;;

  build)
    echo "Building Docker images..."
    $COMPOSE build --no-cache
    ;;

  pull)
    echo "Pulling latest images..."
    $COMPOSE pull
    ;;

  status)
    $COMPOSE ps
    ;;

  update)
    echo "Updating platform..."
    git pull origin main
    $COMPOSE build --no-cache
    $COMPOSE up -d --remove-orphans
    docker system prune -f
    echo "Update complete."
    ;;

  backup-db)
    ts=$(date +%Y%m%d_%H%M%S)
    backup_dir="./backups"
    mkdir -p "$backup_dir"
    echo "Backing up database..."
    # SQLite backup
    if [ -f "./data/platform.db" ]; then
      cp ./data/platform.db "$backup_dir/platform_${ts}.db"
      echo "SQLite backup: $backup_dir/platform_${ts}.db"
    fi
    # PostgreSQL backup (if running)
    $COMPOSE exec -T postgres pg_dump -U swing swing_platform \
      > "$backup_dir/postgres_${ts}.sql" 2>/dev/null && \
      echo "PostgreSQL backup: $backup_dir/postgres_${ts}.sql" || \
      echo "PostgreSQL not running, skipped."
    ;;

  help|*)
    echo ""
    echo "COT Intelligence Platform — Management CLI"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Service commands:"
    echo "  start              Start all Docker services"
    echo "  stop               Stop all services"
    echo "  restart            Restart all services"
    echo "  status             Show service status"
    echo "  logs [service]     Tail logs (optional: dashboard|scheduler|telegram_bot)"
    echo ""
    echo "Scan commands:"
    echo "  scan               Run full market scan now"
    echo "  scan-equities      Scan equity indices only"
    echo "  scan-commodities   Scan commodities only"
    echo "  scan-agriculture   Scan agriculture only"
    echo ""
    echo "Maintenance:"
    echo "  init-db            Initialise database tables"
    echo "  test               Run test suite"
    echo "  build              Rebuild Docker images"
    echo "  update             Pull latest code and redeploy"
    echo "  backup-db          Backup database"
    echo ""
    ;;

esac
