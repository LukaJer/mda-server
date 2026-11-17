#!/bin/bash

# Default values
hostname="mda.local"
execute_db_backup=false

# Function to generate the backup file name based on the current date and time
generate_backup_filename() {
    local current_date_time
    current_date_time=$(date +"%Y_%m_%d-%H_%M_%S")
    echo "backup_${current_date_time}.db"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -db)
            execute_db_backup=true
            shift
            ;;
        -h|--hostname)
            hostname="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ "$execute_db_backup" = true ]; then
    backup_filename=$(generate_backup_filename)
    scp -r mda@"$hostname":/home/mda/repos/mda-server/instance/measurements.db /home/christoph/repositories/mda-server/instance/"$backup_filename"
    cp /home/christoph/repositories/mda-server/instance/"$backup_filename" /home/christoph/repositories/mda-server/instance/measurements.db
else
    ## Variables
    SOURCE_DIR=$(pwd)  # Current directory
    CURRENT_FOLDER_NAME=$(basename "$SOURCE_DIR")  # Name of the current folder
    TARGET_DIR="mda@$hostname:/home/mda/repos/$CURRENT_FOLDER_NAME"  # Path on Raspberry Pi
    EXCLUDE_DIRS=("instance" "venv" "static/node_modules" "static/tiles" ".npm" ".idea" "__pycache__")  # Directories to exclude

    # Build the rsync exclude options
    EXCLUDE_OPTIONS=""
    for dir in "${EXCLUDE_DIRS[@]}"; do
      EXCLUDE_OPTIONS+="--exclude=$dir "
    done

    # rsync command
    eval rsync -av $EXCLUDE_OPTIONS "$SOURCE_DIR/" "$TARGET_DIR"
fi
