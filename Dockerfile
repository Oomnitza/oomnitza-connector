FROM python:3.12.7-slim

ARG APP_DIR=/app
ARG APP_PORT=8000
ARG PYTHON_UNBUFFERED=1
ARG PYTHONDONTWRITEBYTECODE=1
ARG USERNAME=oomuser
ARG USER_UID=1001
ARG USER_GID=$USER_UID

ENV APP_PORT=$APP_PORT
ENV PYTHONUNBUFFERED=$PYTHON_UNBUFFERED
ENV PYTHONDONTWRITEBYTECODE=$PYTHONDONTWRITEBYTECODE

WORKDIR $APP_DIR

RUN apt update && \
    apt install -y build-essential unixodbc unixodbc-dev git openssh-client \
    libsasl2-dev python3-dev libldap2-dev libssl-dev gettext-base \
    && touch /app/config.ini \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -d $APP_DIR --system $USERNAME \
    && chown $USERNAME:$USERNAME /app/config.ini \
    && chmod 755 /app/config.ini \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.ssh && \
    ssh-keyscan bitbucket.org >> /root/.ssh/known_hosts

COPY requirements.txt $APP_DIR

RUN --mount=type=ssh --mount=type=cache,target=/root/.cache \
    pip install -r requirements.txt

COPY --chown=$USERNAME:$USERNAME --chmod=755 docker/entrypoint.sh /docker/entrypoint.sh
COPY --chown=$USERNAME:$USERNAME --chmod=755 docker/config.ini.envsubst /docker/config.ini.envsubst
COPY --chown=$USERNAME:$USERNAME --chmod=755 . $APP_DIR

USER $USERNAME
EXPOSE $APP_PORT

ENTRYPOINT ["/docker/entrypoint.sh"]
CMD ["managed"]