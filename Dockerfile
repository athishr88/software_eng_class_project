# setup project
FROM python:3.12-slim
WORKDIR /passiton/

# Set python binaries
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install dependencies
COPY requirements.txt /passiton/
RUN pip install --no-cache-dir -r requirements.txt

# copy project files
COPY . /passiton/

# run test

# Expose port
EXPOSE 8000

# run on entrance
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
