#/usr/bin/env zsh
echo "$1"
echo "${2:r}.mp4"
SublerCLI -source "$1" -destination "${2:r}.mp4" -optimize
