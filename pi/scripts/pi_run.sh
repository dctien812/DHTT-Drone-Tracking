#!/bin/bash
# chay tren PC (WSL): chay mot file script tren Pi qua SSH. Dung: pi_run.sh <script> [args]
. "$(dirname "$0")/../pi.env" 2>/dev/null || { echo "Loi: thieu pi/pi.env (sao chep tu pi/pi.env.example roi dien PI_USER, PI_HOST)" >&2; exit 1; }; PI="$PI_USER@$PI_HOST"
K="$HOME/.ssh/id_pi_lab"
S="$1"; shift
scp -q -i $K -o IdentitiesOnly=yes "$S" $PI:/tmp/$(basename $S) || exit 1
ssh -i $K -o IdentitiesOnly=yes $PI "bash /tmp/$(basename $S) $*"