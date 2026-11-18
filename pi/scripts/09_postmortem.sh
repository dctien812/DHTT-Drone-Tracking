#!/bin/bash
uptime; vcgencmd get_throttled; vcgencmd measure_temp; vcgencmd pmic_read_adc | grep EXT5V
echo "--- dmesg"; dmesg 2>&1 | grep -i -E 'volt|throttl|oom|out of memory|thermal' | tail -5
echo "--- boots"; journalctl --list-boots --no-pager 2>&1 | tail -3
echo "--- prev boot tail"; journalctl -b -1 --no-pager 2>&1 | tail -25 | cut -c1-200
echo "--- prev boot keywords"; journalctl -b -1 --no-pager 2>&1 | grep -i -E 'under-?volt|oom|out of memory|wlan|thermal|Killed|power' | tail -10 | cut -c1-200
echo "--- grid"; cat ~/dtrack/results/grid.log 2>&1 | cut -c1-420; ls -la ~/dtrack/results