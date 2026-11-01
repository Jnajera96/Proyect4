FROM python:3.13.14-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8

COPY requirements.txt /opt/aiswe/requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r /opt/aiswe/requirements.txt
COPY run_target.py /opt/aiswe/run_target.py
COPY dependency_detector.py /opt/aiswe/dependency_detector.py
LABEL io.aiswe.runner-protocol="2"
LABEL io.aiswe.python-modules="pytest=9.1.1,ruff=0.16.10,iniconfig=2.3.1,packaging=26.3,pluggy=1.6.0,pygments=2.21.0"
ENV HOME=/tmp TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
USER 65532:65532
WORKDIR /tmp
