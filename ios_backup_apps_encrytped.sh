#!/usr/bin/env zsh

# Function to extract app information from an encrypted iPhone backup
function extract_apps_from_encrypted_backup() {
  local backup_dir="$1"
  local manifest_db="$backup_dir/Manifest.db"
  local backup_password

  # Prompt for backup password
  read "backup_password?Enter the backup password: "

  # Check if the encrypted Manifest.db exists
  if [[ ! -f "$manifest_db" ]]; then
    echo "Manifest.db not found in the provided backup directory."
    return 1
  fi

  # Decrypt the Manifest.db file using the password
  local decrypted_manifest="$backup_dir/DecryptedManifest.db"

  openssl enc -aes-256-cbc -d -in "$manifest_db" -out "$decrypted_manifest" -pass pass:"$backup_password" 2>/dev/null

  # Check if decryption succeeded
  if [[ ! -f "$decrypted_manifest" || ! -s "$decrypted_manifest" ]]; then
    echo "Decryption failed or the Manifest.db could not be decrypted."
    return 1
  fi

  # Query the decrypted Manifest.db to get app bundle IDs
  sqlite3 "$decrypted_manifest" \
    "SELECT DISTINCT bundle_id FROM app WHERE bundle_id IS NOT NULL;" | while read -r bundle_id; do
    # Form the App Store URL for each app
    echo "Bundle ID: $bundle_id"
    echo "App Store URL: https://apps.apple.com/app/id$(echo $bundle_id | tr '.' '-')"
    echo
  done

  # Clean up decrypted file
  rm "$decrypted_manifest"
}

# Call the function with the first argument being the backup directory
extract_apps_from_encrypted_backup "$1"
