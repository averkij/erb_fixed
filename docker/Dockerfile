ARG BASE_IMAGE=python:3.9-bookworm
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/erb:/repo HOME=/tmp
WORKDIR /repo
ARG SCM_PRETEND_VERSION
COPY test-requirements.txt /opt/erb/test-requirements.txt
RUN python -m pip install --no-cache-dir pip==24.0 setuptools==69.5.1 wheel==0.43.0
RUN python -m pip install --no-cache-dir -r /opt/erb/test-requirements.txt
COPY repo/ /repo/
COPY container_guard.py /opt/erb/container_guard.py
COPY container_runner.py /opt/erb/runner.py
COPY targets.json /opt/erb/targets.json
RUN if [ -n "$SCM_PRETEND_VERSION" ]; then export SETUPTOOLS_SCM_PRETEND_VERSION="$SCM_PRETEND_VERSION"; fi; \
    if [ -f requirements.txt ]; then python -m pip install --no-cache-dir -r requirements.txt; fi
RUN if [ -f msgpack/_cmsgpack.pyx ] && [ ! -f msgpack/_cmsgpack.c ]; then python -m cython msgpack/_cmsgpack.pyx; fi
RUN if [ -n "$SCM_PRETEND_VERSION" ]; then export SETUPTOOLS_SCM_PRETEND_VERSION="$SCM_PRETEND_VERSION"; fi; \
    python -m pip install --no-cache-dir -e .
RUN python -m pip install --no-cache-dir -r /opt/erb/test-requirements.txt
RUN python -m pip check
RUN python /opt/erb/container_guard.py > /opt/erb/imports.json
RUN python -m pip freeze --all > /opt/erb/packages.txt
RUN find /repo /usr/local/lib -type d -name __pycache__ -prune -exec rm -rf {} + && \
    find /repo -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete && \
    chown -R 10001:10001 /repo && chmod -R a+rX /opt/erb
USER 10001:10001
CMD ["python", "/opt/erb/runner.py"]
