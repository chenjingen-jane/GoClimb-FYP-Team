#!/usr/bin/env bash
set -o errexit

# Render runs this instead of its default build, so install the packages first.
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --noinput
