#!/bin/bash
# PostgreSQL + pgvector Setup Script
# Universal Insurance AI Agent
#
# This script helps you set up PostgreSQL with pgvector for persistent vector storage.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           PostgreSQL + pgvector Setup                        ║"
echo "║           Universal Insurance AI Agent                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)

# Step 1: Check if PostgreSQL is installed
check_postgres() {
    echo -e "${BLUE}Step 1: Checking PostgreSQL installation...${NC}"
    
    if command -v psql &> /dev/null; then
        PG_VERSION=$(psql --version | head -1)
        echo -e "${GREEN}✓ PostgreSQL is installed: $PG_VERSION${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ PostgreSQL not found${NC}"
        return 1
    fi
}

# Install PostgreSQL on macOS
install_postgres_macos() {
    echo -e "${BLUE}Installing PostgreSQL on macOS...${NC}"
    
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}Homebrew not found. Please install Homebrew first:${NC}"
        echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        exit 1
    fi
    
    brew install postgresql@15
    brew services start postgresql@15
    
    # Add to PATH
    echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
    export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
    
    echo -e "${GREEN}✓ PostgreSQL installed and started${NC}"
}

# Install PostgreSQL on Linux
install_postgres_linux() {
    echo -e "${BLUE}Installing PostgreSQL on Linux...${NC}"
    
    # Detect package manager
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y postgresql postgresql-contrib
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y postgresql-server postgresql-contrib
        sudo postgresql-setup --initdb
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    else
        echo -e "${RED}Unknown package manager. Please install PostgreSQL manually.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ PostgreSQL installed and started${NC}"
}

# Step 2: Install pgvector extension
install_pgvector() {
    echo -e "${BLUE}Step 2: Installing pgvector extension...${NC}"
    
    if [[ "$OS" == "macos" ]]; then
        brew install pgvector
    elif [[ "$OS" == "linux" ]]; then
        # Try apt first
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y postgresql-15-pgvector 2>/dev/null || {
                echo -e "${YELLOW}pgvector not in apt, installing from source...${NC}"
                install_pgvector_from_source
            }
        else
            install_pgvector_from_source
        fi
    fi
    
    echo -e "${GREEN}✓ pgvector installed${NC}"
}

# Install pgvector from source (fallback)
install_pgvector_from_source() {
    echo -e "${BLUE}Installing pgvector from source...${NC}"
    
    # Get pg_config path
    PG_CONFIG=$(which pg_config)
    if [ -z "$PG_CONFIG" ]; then
        echo -e "${RED}pg_config not found. Make sure PostgreSQL development headers are installed.${NC}"
        exit 1
    fi
    
    # Clone and build
    cd /tmp
    git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
    cd pgvector
    make
    sudo make install
    cd -
    rm -rf /tmp/pgvector
}

# Step 3: Create database and enable extension
setup_database() {
    echo -e "${BLUE}Step 3: Creating database and enabling pgvector...${NC}"
    
    # Database configuration
    DB_NAME="${DB_NAME:-insur}"
    DB_USER="${DB_USER:-insur_user}"
    DB_PASS="${DB_PASS:-insur_password}"
    
    echo -e "${CYAN}Database: $DB_NAME${NC}"
    echo -e "${CYAN}User: $DB_USER${NC}"
    
    # Create user and database
    if [[ "$OS" == "macos" ]]; then
        # macOS - current user is superuser
        psql postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || echo "User may already exist"
        psql postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo "Database may already exist"
        psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
        psql $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"
    else
        # Linux - use sudo to run as postgres user
        sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || echo "User may already exist"
        sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || echo "Database may already exist"
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
        sudo -u postgres psql $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"
    fi
    
    echo -e "${GREEN}✓ Database '$DB_NAME' created with pgvector extension${NC}"
}

# Step 4: Test connection
test_connection() {
    echo -e "${BLUE}Step 4: Testing connection...${NC}"
    
    DB_NAME="${DB_NAME:-insur}"
    DB_USER="${DB_USER:-insur_user}"
    DB_PASS="${DB_PASS:-insur_password}"
    
    # Test pgvector
    PGPASSWORD=$DB_PASS psql -h localhost -U $DB_USER -d $DB_NAME -c "SELECT vector '[1,2,3]'::vector;" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ pgvector is working!${NC}"
    else
        echo -e "${RED}✗ pgvector test failed${NC}"
        exit 1
    fi
}

# Step 5: Generate .env config
generate_env_config() {
    echo -e "${BLUE}Step 5: Generating .env configuration...${NC}"
    
    DB_NAME="${DB_NAME:-insur}"
    DB_USER="${DB_USER:-insur_user}"
    DB_PASS="${DB_PASS:-insur_password}"
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    
    DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
    
    echo ""
    echo -e "${CYAN}Add these lines to your .env file:${NC}"
    echo ""
    echo -e "${GREEN}# PostgreSQL + pgvector (Production)${NC}"
    echo -e "${GREEN}DATABASE_URL=$DATABASE_URL${NC}"
    echo -e "${GREEN}VECTOR_STORE_TYPE=pgvector${NC}"
    echo ""
}

# Main menu
show_menu() {
    echo ""
    echo -e "${BLUE}What would you like to do?${NC}"
    echo "1) Full setup (install everything)"
    echo "2) Just create database (PostgreSQL already installed)"
    echo "3) Just enable pgvector (database already exists)"
    echo "4) Test connection"
    echo "5) Show .env configuration"
    echo "6) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice
    
    case $choice in
        1)
            if ! check_postgres; then
                if [[ "$OS" == "macos" ]]; then
                    install_postgres_macos
                else
                    install_postgres_linux
                fi
            fi
            install_pgvector
            setup_database
            test_connection
            generate_env_config
            ;;
        2)
            setup_database
            test_connection
            generate_env_config
            ;;
        3)
            DB_NAME="${DB_NAME:-insur}"
            if [[ "$OS" == "macos" ]]; then
                psql $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"
            else
                sudo -u postgres psql $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"
            fi
            echo -e "${GREEN}✓ pgvector extension enabled${NC}"
            ;;
        4)
            test_connection
            ;;
        5)
            generate_env_config
            ;;
        6)
            echo "Bye!"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            ;;
    esac
}

# Run
if [ "$1" == "--auto" ]; then
    # Automatic mode for CI/CD
    if ! check_postgres; then
        if [[ "$OS" == "macos" ]]; then
            install_postgres_macos
        else
            install_postgres_linux
        fi
    fi
    install_pgvector
    setup_database
    test_connection
    generate_env_config
else
    show_menu
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Setup Complete!                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "1. Update your .env file with the DATABASE_URL shown above"
echo "2. Set VECTOR_STORE_TYPE=pgvector in .env"
echo "3. Run migrations: ./scripts/db.sh upgrade"
echo "4. Restart your server"
echo ""

