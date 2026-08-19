ARG LITELLM_IMAGE=ghcr.io/berriai/litellm:main-stable
FROM ${LITELLM_IMAGE}

WORKDIR /app
COPY app /app/app
COPY config.yaml /app/config.yaml

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 4000

ENTRYPOINT ["litellm"]
CMD ["--config", "/app/config.yaml", "--host", "0.0.0.0", "--port", "4000"]
