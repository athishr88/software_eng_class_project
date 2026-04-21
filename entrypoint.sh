#!/bin/sh
set -e

echo "Running migrations"
python3 manage.py migrate

echo "Loading seed data"
python3 manage.py loaddata seed_data.json

echo "Starting server"
python3 manage.py runserver 0.0.0.0:8000
# TODO replace line above with production command once in production

