#!/bin/bash
# chay tren PC (WSL): chay mot file script tren Pi qua SSH. Dung: pi_run.sh <script> [args]
PI="dctien812@192.168.1.91"; K="$HOME/.ssh/id_pi_lab"
S="$1"; shift
scp -q -i $K -o IdentitiesOnly=yes "$S" $PI:/tmp/$(basename $S) || exit 1
ssh -i $K -o IdentitiesOnly=yes $PI "bash /tmp/$(basename $S) $*"