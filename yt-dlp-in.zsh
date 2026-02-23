#!/usr/bin/env zsh

  typeset -A output_dirs
  output_dirs=(
      dl "$ICLOUD/Downloads"
      yt "$ICLOUD/media/yt"
      x "$HOME/.x"
  )

  # Use 'dl' as default if no directory specified or invalid directory
  if [[ -z "$1" || -z "${output_dirs[$1]}" ]]; then
      if [[ -n "$1" && -z "${output_dirs[$1]}" ]]; then
          print "Invalid directory '$1'. Using default 'dl'."
      fi
      selected_dir="dl"
      # Don't shift if we're using default (no valid first arg)
      if [[ -n "$1" && -z "${output_dirs[$1]}" ]]; then
          shift
      fi
  else
      selected_dir="$1"
      shift
  fi

  export YT_OUTPUT_DIR="${output_dirs[$selected_dir]}"

  $HOME/.local/bin/yt-dlp --cookies-from-browser firefox --output "$YT_OUTPUT_DIR/%(title)s.%(ext)s" "$@"