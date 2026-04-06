#!/usr/bin/bash
set -e

cd /home/ubuntu/software_eng_class_project

sed -i 's/\[]/\["34.226.244.102"]/' passiton/settings.py

/home/ubuntu/env/bin/python manage.py migrate
/home/ubuntu/env/bin/python manage.py collectstatic --noinput
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
