#!/bin/bash
. "$(dirname "$0")/../pi.env" 2>/dev/null || { echo "Loi: thieu pi/pi.env (sao chep tu pi/pi.env.example roi dien PI_USER, PI_HOST)" >&2; exit 1; }; PI="$PI_USER@$PI_HOST"
ssh -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes $PI "$@"
