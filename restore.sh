#!/bin/bash

SOURCE_DB="./app/problems.db"
BACKUP_DB="./app/backups/problems_backup.db"

# Check backup database exists
if [ -f "$BACKUP_DB" ]; then

    # Stop containers, copy backup db to source db and start containers
    docker compose down
    cp "$BACKUP_DB" "$SOURCE_DB"
    docker compose up -d

    # Verify the restore operation
    if [ -f "$SOURCE_DB" ]; then
        echo "Restore of '$SOURCE_DB' from '$BACKUP_DB' completed successfully."
    else
        echo "Restore failed: '$SOURCE_DB' was not created."
    fi

else
    echo "Backup database '$BACKUP_DB' does not exist."
fi
