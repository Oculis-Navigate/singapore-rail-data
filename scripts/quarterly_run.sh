#!/bin/bash
#
# Quarterly MRT Data Pipeline Runner
# 
# This script is designed to be run as a cron job on a quarterly basis
# to update the MRT transit data with the latest information.
#
# Cron schedule (run quarterly on the 1st of January, April, July, October at 2 AM):
# 0 2 1 1,4,7,10 * /path/to/mrt-data/scripts/quarterly_run.sh
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/quarterly_run_$TIMESTAMP.log"
VENV_DIR="$PROJECT_ROOT/.venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1${NC}" | tee -a "$LOG_FILE"
}

# Ensure we're in the project directory
cd "$PROJECT_ROOT"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Start logging
log "Starting quarterly MRT data pipeline run"
log "Project root: $PROJECT_ROOT"
log "Log file: $LOG_FILE"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    error "uv is not installed or not in PATH"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    error "Virtual environment not found at $VENV_DIR"
    error "Please run 'uv sync' first to set up the environment"
    exit 1
fi

# Check if configuration exists
if [ ! -f "config/pipeline.yaml" ]; then
    error "Pipeline configuration not found: config/pipeline.yaml"
    exit 1
fi

# Function to run pipeline stage
run_stage() {
    local stage="$1"
    log "Running stage: $stage"
    
    if uv run python scripts/run_pipeline.py --stage "$stage" --config config/pipeline.yaml 2>&1 | tee -a "$LOG_FILE"; then
        success "Stage $stage completed successfully"
        return 0
    else
        error "Stage $stage failed"
        return 1
    fi
}

# Function to validate output
validate_output() {
    log "Validating pipeline output"
    
    if uv run python scripts/validate_output.py --config config/pipeline.yaml --verbose 2>&1 | tee -a "$LOG_FILE"; then
        success "Output validation passed"
        return 0
    else
        warning "Output validation failed (may be acceptable)"
        return 1
    fi
}

# Function to cleanup old logs (keep last 30 days)
cleanup_logs() {
    log "Cleaning up old log files (keeping last 30 days)"
    find "$LOG_DIR" -name "quarterly_run_*.log" -mtime +30 -delete 2>/dev/null || true
    log "Log cleanup completed"
}

# Function to create output symlink if configured
create_symlink() {
    local latest_output
    latest_output=$(ls -t outputs/*.json 2>/dev/null | head -1) || {
        warning "No output files found to symlink"
        return 0
    }
    
    if grep -q "symlink_latest: true" config/pipeline.yaml; then
        ln -sf "$(basename "$latest_output")" outputs/latest.json
        log "Created symlink: outputs/latest.json -> $latest_output"
    fi
}

# Main execution
main() {
    local exit_code=0
    
    log "Starting pipeline execution"
    
    # Run the full pipeline
    if uv run python scripts/run_pipeline.py --config config/pipeline.yaml 2>&1 | tee -a "$LOG_FILE"; then
        success "Full pipeline completed successfully"
    else
        error "Pipeline execution failed"
        exit_code=1
    fi
    
    # Validate output (even if pipeline failed, we might have partial results)
    if ! validate_output; then
        warning "Output validation had issues, but continuing..."
    fi
    
    # Create symlink if configured
    create_symlink
    
    # Cleanup old logs
    cleanup_logs
    
    # Final status
    if [ $exit_code -eq 0 ]; then
        success "Quarterly MRT data pipeline run completed successfully"
        log "Log file: $LOG_FILE"
    else
        error "Quarterly MRT data pipeline run failed"
        error "Check log file for details: $LOG_FILE"
    fi
    
    return $exit_code
}

# Handle script interruption
trap 'error "Script interrupted"; exit 130' INT TERM

# Run main function
main "$@"

exit $?