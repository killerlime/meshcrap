FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="Meshcrap" \
      org.opencontainers.image.source="https://github.com/killerlime/meshcrap"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/meshcrap
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip check \
    && pip freeze > /opt/meshcrap/BUILD-DEPENDENCIES.txt \
    && groupadd --gid 10001 meshcrap \
    && useradd --uid 10001 --gid 10001 --no-create-home meshcrap \
    && mkdir /data && chown 10001:10001 /data
COPY meshcrap.py setup_wizard.py schema.sql config.example.json LICENSE THIRD_PARTY_NOTICES.md ./
COPY licenses/ ./licenses/
COPY source/ ./source/
COPY deploy/docker/entrypoint.py ./container_entrypoint.py
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "/opt/meshcrap/container_entrypoint.py"]
CMD ["serve"]
