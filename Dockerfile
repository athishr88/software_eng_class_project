# setup project
FROM python:3.12-bookworm
WORKDIR /passiton/

# install dependencies
COPY requirements.txt /passiton/
RUN pip install --no-cache-dir -r requirements.txt

# copy project files
COPY . /passiton/

# run test

# Expose port
EXPOSE 8000

# run on entrance
RUN python3 manage.py migrate
RUN python3 manage.py loaddata seed_data.json
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
