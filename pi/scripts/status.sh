#!/bin/bash
ps aux | grep -E 'pip|03_torch' | grep -v grep | cut -c1-160; du -sh ~/dtrack; free -m | head -2
