plist="$HOME/Library/LaunchAgents/com.user.batterycheck.plist"
script_file="$HOME/dev/scripts/_launchd/battery_check.sh"

mkdir -p "$(dirname "$script_file")"

cat > "$script_file" << 'EOF'
capacity=$(system_profiler SPPowerDataType -json | jq -r '."SPPowerDataType"[0].sppower_battery_health_info.sppower_battery_health_maximum_capacity' | tr -d '%')
if [ "$capacity" -ge 81 ]; then
  osascript -e "display notification \"Maybe take it in for service\" with title \"Battery Status ${capacity}%\""
  open "https://support.apple.com/mac/repair"
fi
EOF

chmod +x "$script_file"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.user.batterycheck</string>
  <key>ProgramArguments</key><array><string>$script</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
EOF

launchctl load "$plist"
