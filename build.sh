#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py makemigrations ems
python manage.py migrate ems
python manage.py migrate
python manage.py create_superuser
