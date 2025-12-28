#!/bin/bash
# Database management helper script for Universal Insurance AI Agent
# Usage: ./scripts/db.sh <command> [args]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Help message
show_help() {
    echo -e "${BLUE}Database Management Script${NC}"
    echo ""
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  migrate <message>  Create a new migration with auto-detection"
    echo "  upgrade            Apply all pending migrations"
    echo "  downgrade [n]      Rollback n migrations (default: 1)"
    echo "  status             Show current migration status"
    echo "  history            Show migration history"
    echo "  reset              Reset database (DANGEROUS - drops all tables)"
    echo "  init               Initialize fresh database with all migrations"
    echo "  help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 migrate 'add user roles'"
    echo "  $0 upgrade"
    echo "  $0 downgrade 2"
    echo "  $0 status"
}

# Check if alembic is installed
check_alembic() {
    if ! command -v alembic &> /dev/null; then
        echo -e "${RED}Error: alembic is not installed${NC}"
        echo "Install it with: pip install alembic"
        exit 1
    fi
}

# Create a new migration
cmd_migrate() {
    check_alembic
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Migration message required${NC}"
        echo "Usage: $0 migrate 'description of changes'"
        exit 1
    fi
    
    echo -e "${BLUE}Creating migration: $1${NC}"
    alembic revision --autogenerate -m "$1"
    echo -e "${GREEN}✓ Migration created successfully${NC}"
    echo ""
    echo -e "${YELLOW}⚠ Please review the generated migration before applying!${NC}"
}

# Apply migrations
cmd_upgrade() {
    check_alembic
    echo -e "${BLUE}Applying pending migrations...${NC}"
    alembic upgrade head
    echo -e "${GREEN}✓ Migrations applied successfully${NC}"
}

# Rollback migrations
cmd_downgrade() {
    check_alembic
    local steps="${1:-1}"
    
    echo -e "${YELLOW}Rolling back $steps migration(s)...${NC}"
    read -p "Are you sure? (y/N) " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        alembic downgrade "-$steps"
        echo -e "${GREEN}✓ Rollback complete${NC}"
    else
        echo "Cancelled."
    fi
}

# Show status
cmd_status() {
    check_alembic
    echo -e "${BLUE}Current migration status:${NC}"
    echo ""
    alembic current
    echo ""
    echo -e "${BLUE}Pending migrations:${NC}"
    alembic history --indicate-current | head -20
}

# Show history
cmd_history() {
    check_alembic
    echo -e "${BLUE}Migration history:${NC}"
    alembic history --verbose
}

# Reset database (dangerous!)
cmd_reset() {
    echo -e "${RED}⚠ WARNING: This will DROP ALL TABLES and recreate them!${NC}"
    read -p "Type 'RESET' to confirm: " confirm
    
    if [ "$confirm" = "RESET" ]; then
        echo -e "${YELLOW}Dropping all tables...${NC}"
        alembic downgrade base 2>/dev/null || true
        echo -e "${BLUE}Applying all migrations...${NC}"
        alembic upgrade head
        echo -e "${GREEN}✓ Database reset complete${NC}"
    else
        echo "Cancelled."
    fi
}

# Initialize fresh database
cmd_init() {
    check_alembic
    echo -e "${BLUE}Initializing database...${NC}"
    alembic upgrade head
    echo -e "${GREEN}✓ Database initialized${NC}"
}

# Main command router
case "${1:-help}" in
    migrate)
        cmd_migrate "$2"
        ;;
    upgrade)
        cmd_upgrade
        ;;
    downgrade)
        cmd_downgrade "$2"
        ;;
    status)
        cmd_status
        ;;
    history)
        cmd_history
        ;;
    reset)
        cmd_reset
        ;;
    init)
        cmd_init
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

