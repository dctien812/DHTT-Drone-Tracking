#!/bin/bash
ssh -i $HOME/.ssh/id_pi_lab -o IdentitiesOnly=yes dctien812@192.168.1.91 "$@"
