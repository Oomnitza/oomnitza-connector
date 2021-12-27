FROM python:3.6-buster

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

ARG APP_USER=appuser

RUN groupadd -r ${APP_USER} -g 1000 && \
    useradd --no-log-init --create-home -u 1000 -r -g ${APP_USER} ${APP_USER}

ARG APP_DIR=/home/${APP_USER}/oomnitza-connector/
ARG CONFIG_DIR=/home/${APP_USER}/config/
ARG EXP_DIR=/home/${APP_USER}/exp/

RUN echo $APP_DIR && mkdir ${APP_DIR} && mkdir ${CONFIG_DIR} && mkdir ${EXP_DIR} && chown ${APP_USER}:${APP_USER} ${APP_DIR} ${CONFIG_DIR} ${EXP_DIR}

COPY ./requirements.txt ${APP_DIR}

RUN apt-get -q update && \
    apt-get -qy install libsasl2-dev \
                        python-dev \
                        libldap2-dev \
                        libssl-dev \
                        build-essential \
                        unixodbc \
                        unixodbc-dev && \
    rm -rf /var/lib/apt/lists/*

RUN set -ex &&\
    pip install --upgrade pip && \
    pip install --no-cache-dir -r ${APP_DIR}requirements.txt

COPY --chown=${APP_USER}:${APP_USER} . ${APP_DIR}

USER ${APP_USER}:${APP_USER}

WORKDIR ${APP_DIR}

RUN python connector.py generate-ini
