#!/bin/bash

# Script to restore database for the Cayuman project
# This script first drops all smiles tables and then restores from backup

PROJECT_DIR=/Users/roberto/dev/cayuman

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting database restoration process..."
echo "First, dropping all smiles tables..."

# Execute the drop tables script
cat "$PROJECT_DIR/drop-smiles-tables.sql" | docker compose exec -T db mysql -ucayuman -pcayuman_password cayuman

if [ $? -eq 0 ]; then
    echo "✅ Successfully dropped all smiles tables."
else
    echo "❌ Failed to drop smiles tables. Aborting."
    exit 1
fi

echo "Now restoring from backup..."

# Execute the backup restoration
cat "$PROJECT_DIR/db-backup.sql" | docker compose exec -T db mysql -ucayuman -pcayuman_password cayuman

if [ $? -eq 0 ]; then
    echo "✅ Database restoration completed successfully!"
else
    echo "❌ Failed to restore database from backup."
    exit 1
fi

echo "Database restoration process completed."
