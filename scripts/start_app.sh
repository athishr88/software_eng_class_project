#!/usr/bin/bash
APP_DIR=/home/ubuntu/software_eng_class_project
# Ensure app files are writable by Gunicorn user (ubuntu); fixes root-owned artifacts from deploys.
sudo chown -R ubuntu:ubuntu "$APP_DIR"
source /home/ubuntu/env/bin/activate
cd /home/ubuntu/software_eng_class_project

python manage.py migrate
python manage.py collectstatic --noinput

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
