capacity=$(system_profiler SPPowerDataType -json | jq -r '."SPPowerDataType"[0].sppower_battery_health_info.sppower_battery_health_maximum_capacity' | tr -d '%')
echo $capacity
if [ "$capacity" -le 81 ]; then
  osascript -e "display notification \"Maybe take it in for service\" with title \"Battery Status ${capacity}%\""
  open "https://support.apple.com/mac/repair"
fi
