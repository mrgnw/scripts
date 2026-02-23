#!/usr/bin/env zsh

# Function to extract app information from an unencrypted iPhone backup
function extract_apps_from_backup() {
  local backup_dir="$1"
  local manifest_db="$backup_dir/Manifest.db"

  # Check if the Manifest.db exists
  if [[ ! -f "$manifest_db" ]]; then
    echo "Manifest.db not found in the provided backup directory."
    return 1
  fi

  # Query the Manifest.db to get app bundle IDs
  sqlite3 "$manifest_db" \
    "SELECT DISTINCT bundle_id FROM app WHERE bundle_id IS NOT NULL;" | while read -r bundle_id; do
    # Form the App Store URL for each app
    echo "Bundle ID: $bundle_id"
    echo "App Store URL: https://apps.apple.com/app/id$(echo $bundle_id | tr '.' '-')"
    echo
  done
}

# Call the function with the first argument being the backup directory
extract_apps_from_backup "$1"
