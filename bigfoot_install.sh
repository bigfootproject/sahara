#!/bin/bash

source /opt/savanna-venv/bin/activate

python /opt/savanna/setup.py install

service savanna_git restart

tail /var/log/upstart/savanna_git.log

