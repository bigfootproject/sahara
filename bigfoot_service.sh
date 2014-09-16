#!/bin/bash

cd /opt/sahara

tox -e venv -- sahara-all --config-file etc/sahara/sahara.conf --log-file /var/log/upstart/sahara_git.log

