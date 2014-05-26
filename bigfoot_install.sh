#!/bin/bash

source /opt/sahara-venv/bin/activate

python /opt/sahara/setup.py install

echo
echo "restarting sahara"
service sahara_git restart

echo "Check /var/log/upstart/sahara_git.log to see startup errors"

