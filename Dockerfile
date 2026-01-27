FROM python:3.10.12-slim as base 
# This needs fixed, but pandas and numpy dependencies were being weird with 3.12 so I need to resolve that. Pin to .10.12 for now hashtag techdebt

ENV POETRY_HOME=/opt/poetry
ENV POETRY_VERSION=2.1.3
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV POETRY_VIRTUALENVS_CREATE=1
ENV PATH=${PATH}:${POETRY_HOME}/bin

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --uid "${UID}" \
    appuser

FROM base as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl 

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR $POETRY_HOME

COPY poetry.lock pyproject.toml README.md ./
COPY ./storygrabber ./storygrabber

RUN poetry check

RUN poetry install

FROM base as production

WORKDIR /app 
COPY --from=builder $POETRY_HOME $POETRY_HOME
COPY --from=builder $POETRY_HOME/.venv .venv

COPY ./poetry.lock \
        ./pyproject.toml \
        ./README.md \
        ./
COPY ./storygrabber ./storygrabber

RUN poetry install

COPY entrypoint.sh ./

RUN chmod +x ./entrypoint.sh
RUN mkdir -p /app/cache && chown -R appuser:appuser /app/cache || true

ENTRYPOINT [ "./entrypoint.sh" ]