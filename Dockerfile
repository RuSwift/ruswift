FROM python:3.9 as base

ARG VERSION='0.0'

RUN apt-get update && \
  apt-get install -y coreutils iputils-ping
ENV LANG C.UTF-8

# Unlimited db connections
ENV DATABASE_CONN_MAX_AGE 0

# Copy project files and install dependencies
ADD app /app
WORKDIR /app

RUN pip install -U pip poetry==1.8.5
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes
RUN pip install -r requirements.txt
RUN chmod +x /app/wait-for-it.sh

# Environment
ENV PYTHONPATH=..:/app:${PYTHONPATH}

#FROM base as supervisor
#RUN apt-get install -y supervisor
#COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
#CMD ["/usr/bin/supervisord"]

#FROM base AS web
#EXPOSE 80
#HEALTHCHECK --interval=60s --timeout=3s --start-period=30s \
#  CMD curl -f http://localhost/health/liveness_probe || exit 1
# FIRE!!!
#CMD /app/wait-for-it.sh ${DATABASE_HOST}:${DATABASE_PORT-5432} --timeout=60 && \
#  python manage.py migrate && \
#  gunicorn --bind 0.0.0.0:80 --workers=4 settings.wsgi
