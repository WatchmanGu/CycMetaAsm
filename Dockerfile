# syntax=docker/dockerfile:1.7
# Build docker image for CycMetaAsm workflow
ARG MICROMAMBA_IMAGE=mambaorg/micromamba:latest

FROM ${MICROMAMBA_IMAGE} AS builder

USER root
ARG ROSA_VERSION=1.1.0
ARG ROSA_ARCHIVE_SHA256=129469eb3a4b4b3565c9b4fa2689e19c136859446213880189825a3949793752

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's@deb.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's@security.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's@deb.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list; \
      sed -i 's@security.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential \
      bzip2 \
      ca-certificates \
      coreutils \
      time \
      unzip \
      wget \
      zip; \
    rm -rf /var/lib/apt/lists/*

COPY --from=cycloneseq_report_template . /tmp/cycloneseq-report-template/
COPY cycmetaasm-tools-conda-linux-64.lock /tmp/cycmetaasm-tools-conda-linux-64.lock
COPY lorbin-conda-linux-64.lock /tmp/lorbin-conda-linux-64.lock
COPY rosa-bio-linux-64.lock /tmp/rosa-bio-linux-64.lock
COPY cycloneseq-report-conda-linux-64.lock /tmp/cycloneseq-report-conda-linux-64.lock
COPY cycloneseq-report-build-conda-linux-64.lock /tmp/cycloneseq-report-build-conda-linux-64.lock

RUN set -eux; \
    for lock in \
      /tmp/cycmetaasm-tools-conda-linux-64.lock \
      /tmp/lorbin-conda-linux-64.lock \
      /tmp/rosa-bio-linux-64.lock \
      /tmp/cycloneseq-report-conda-linux-64.lock \
      /tmp/cycloneseq-report-build-conda-linux-64.lock; do \
      sed -i \
        -e 's@https://conda.anaconda.org/conda-forge@https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge@g' \
        -e 's@https://conda.anaconda.org/bioconda@https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/bioconda@g' \
        -e 's@https://conda.anaconda.org/anaconda@https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main@g' \
        "$lock"; \
    done; \
    micromamba create -y -n cycmetaasm_tools --file /tmp/cycmetaasm-tools-conda-linux-64.lock && \
    micromamba create -y -n lorbin_env --file /tmp/lorbin-conda-linux-64.lock && \
    micromamba create -y -n bio --file /tmp/rosa-bio-linux-64.lock && \
    micromamba create -y -n cycloneseq-report --file /tmp/cycloneseq-report-conda-linux-64.lock && \
    micromamba create -y -n cycloneseq-report-build --file /tmp/cycloneseq-report-build-conda-linux-64.lock && \
    micromamba clean -a -y

# LorBin's Python package is vendored; all heavy scientific dependencies are in
# the CPU-only lorbin_env lock.
COPY vendor/lorbin-0.1.0.tar.gz /tmp/lorbin-0.1.0.tar.gz
RUN /opt/conda/envs/lorbin_env/bin/python -m pip install --no-build-isolation --no-cache-dir --no-deps /tmp/lorbin-0.1.0.tar.gz && \
    rm -f /tmp/lorbin-0.1.0.tar.gz && \
    ln -sf /opt/conda/envs/lorbin_env/bin/LorBin /opt/conda/envs/cycmetaasm_tools/bin/LorBin

# Rosa is isolated to the bio env while its vendored wheel archive checksum is
# verified against the Process16S unified image asset.
COPY vendor/rosa-${ROSA_VERSION}.wheel.tar.gz /tmp/rosa.tar.gz
RUN echo "${ROSA_ARCHIVE_SHA256}  /tmp/rosa.tar.gz" | sha256sum -c - && \
    mkdir -p /tmp/rosa && \
    tar -xzf /tmp/rosa.tar.gz -C /tmp/rosa && \
    /opt/conda/envs/bio/bin/python -m pip install --no-deps --no-cache-dir /tmp/rosa/rosa-*/*.whl && \
    rm -rf /tmp/rosa /tmp/rosa.tar.gz

# Build the Cythonized report wheel in a throwaway build env, then install only
# the wheel into the runtime report env.
RUN /opt/conda/envs/cycloneseq-report-build/bin/python -m pip wheel \
      --no-deps \
      --no-build-isolation \
      -w /tmp/cycloneseq-report-wheel \
      /tmp/cycloneseq-report-template && \
    /opt/conda/envs/cycloneseq-report/bin/python -m pip install --no-deps --no-cache-dir /tmp/cycloneseq-report-wheel/*.whl && \
    rm -rf /tmp/cycloneseq-report-template /tmp/cycloneseq-report-wheel /opt/conda/envs/cycloneseq-report-build

# NextPolish can lose calgs.so in its shared library directory during env solves.
COPY src/lib/*.so /opt/conda/envs/cycmetaasm_tools/share/nextpolish-1.4.1/lib/

COPY build/CycMetaAsm.bin /usr/local/bin/cycmetaasm
RUN chmod +x /usr/local/bin/cycmetaasm && \
    find /opt/conda/envs -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \) -prune -exec rm -rf '{}' + && \
    find /opt/conda/envs -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.a' -o -name '*.la' -o -name '*.js.map' \) -delete && \
    rm -rf /opt/conda/pkgs /root/.cache /tmp/*

FROM ${MICROMAMBA_IMAGE} AS runtime

USER root
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's@deb.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's@security.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's@deb.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list; \
      sed -i 's@security.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      bzip2 \
      ca-certificates \
      coreutils \
      time \
      zip; \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/conda/envs/cycmetaasm_tools /opt/conda/envs/cycmetaasm_tools
COPY --from=builder /opt/conda/envs/lorbin_env /opt/conda/envs/lorbin_env
COPY --from=builder /opt/conda/envs/bio /opt/conda/envs/bio
COPY --from=builder /opt/conda/envs/cycloneseq-report /opt/conda/envs/cycloneseq-report
COPY --from=builder /usr/local/bin/cycmetaasm /usr/local/bin/cycmetaasm

RUN ln -sf /opt/conda/envs/lorbin_env/bin/LorBin /usr/local/bin/LorBin && \
    ln -sf /opt/conda/envs/bio/bin/rosa /usr/local/bin/rosa && \
    ln -sf /opt/conda/envs/cycloneseq-report/bin/cycloneseq-report /usr/local/bin/cycloneseq-report && \
    mkdir -p /tmp/matplotlib /tmp/.cache /var/cache/fontconfig && \
    chmod -R 777 /tmp/matplotlib /tmp/.cache /var/cache/fontconfig

ENV PATH=/usr/local/bin:/opt/conda/envs/cycmetaasm_tools/bin:/opt/conda/envs/lorbin_env/bin:/opt/conda/envs/bio/bin:/opt/conda/envs/cycloneseq-report/bin:$PATH
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV XDG_CACHE_HOME=/tmp/.cache
ENV FONTCONFIG_PATH=/etc/fonts
ENV FONTCONFIG_FILE=fonts.conf

WORKDIR /data
CMD ["cycmetaasm", "--help"]
