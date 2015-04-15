#!/bin/sh

tox -e venv -- sahara-db-manage --config-file etc/sahara/sahara.conf upgrade head
