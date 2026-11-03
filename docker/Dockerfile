ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/erb:/repo HOME=/tmp
WORKDIR /repo
COPY repo/ /repo/
COPY test-requirements.txt /opt/erb/test-requirements.txt
COPY container_guard.py /opt/erb/container_guard.py
COPY container_runner.py /opt/erb/runner.py
COPY targets.json /opt/erb/targets.json
RUN python -m pip install --no-cache-dir pip==24.0 setuptools==69.5.1 wheel==0.43.0
RUN if [ -f requirements.txt ]; then python -m pip install --no-cache-dir -r requirements.txt; fi
RUN python -m pip install --no-cache-dir -e .
RUN python -m pip install --no-cache-dir -r /opt/erb/test-requirements.txt
RUN python -m pip check
RUN python /opt/erb/container_guard.py > /opt/erb/imports.json
RUN python -m pip freeze --all > /opt/erb/packages.txt
RUN find /repo /usr/local/lib -type d -name __pycache__ -prune -exec rm -rf {} + && \
    find /repo -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete && \
    chown -R 10001:10001 /repo && chmod -R a+rX /opt/erb
USER 10001:10001
CMD ["python", "/opt/erb/runner.py"]
