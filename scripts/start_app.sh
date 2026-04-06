#!/usr/bin/bash
set -e

APP_DIR=/home/ubuntu/software_eng_class_project
PYTHON=/home/ubuntu/env/bin/python

cd "$APP_DIR"

sed -i 's/\[]/\["34.226.244.102"]/' passiton/settings.py

"$PYTHON" manage.py migrate
"$PYTHON" manage.py collectstatic --noinput
sudo service gunicorn restart
sudo service nginx restart
#sudo tail -f /var/log/nginx/error.log
#sudo systemctl reload nginx
#sudo tail -f /var/log/nginx/error.log
#sudo nginx -t
#sudo systemctl restart gunicorn
#sudo systemctl status gunicorn
#sudo systemctl status nginx
# Check the status
#systemctl status gunicorn
# Restart:
#systemctl restart gunicorn
#sudo systemctl status nginx
