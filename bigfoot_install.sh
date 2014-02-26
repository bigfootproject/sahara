#!/bin/bash

source /opt/savanna-venv/bin/activate

python /opt/savanna/setup.py install

echo
echo "restarting savanna"
service savanna_git restart

echo "Check /var/log/upstart/savanna_git.log to see startup errors"

