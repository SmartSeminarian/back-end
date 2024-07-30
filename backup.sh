#!/bin/bash

# Paths to the source and backup databases
SOURCE_DB="./data/$1"
BACKUP_DB="./data/backups/backup-$1"

mkdir -p ./data/backups

# Check source database exists
if [ -f "$SOURCE_DB" ]; then
    # Backup using sqlite3 command (.backup)
    sqlite3 "$SOURCE_DB" ".backup '$BACKUP_DB'"

    # Check the backup was created successfully
    if [ -f "$BACKUP_DB" ]; then
        echo "Backup of '$SOURCE_DB' completed successfully to '$BACKUP_DB'"
    else
        echo "Backup failed: '$BACKUP_DB' was not created."
    fi

else
    echo "Source database '$SOURCE_DB' does not exist."
fi

