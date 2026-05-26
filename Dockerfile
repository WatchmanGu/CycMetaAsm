# syntax=docker/dockerfile:1.7
# Build docker image for CycMetaAsm workflow
FROM mambaorg/micromamba:latest AS runtime

# Use Tsinghua mirrors for Debian/Ubuntu packages in the micromamba base
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
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      bzip2 \
      build-essential \
      ca-certificates \
      time \
      coreutils \
      wget \
      curl \
      unzip \
      zip \
      && rm -rf /var/lib/apt/lists/*

# Try to use pre-generated lock files. The main environment contains the
# CycMetaAsm runtime tools; LorBin, Rosa, and the report generator are isolated
# to preserve their locked dependency stacks.

COPY --from=cycloneseq_report_template . /tmp/cycloneseq-report-template/
COPY conda-linux-64.lock /tmp/conda-linux-64.lock
COPY lorbin-conda-linux-64.lock /tmp/lorbin-conda-linux-64.lock
COPY rosa-bio-linux-64.lock /tmp/rosa-bio-linux-64.lock
RUN micromamba create -y -n cycmetaasm --file /tmp/conda-linux-64.lock && \
    micromamba clean -a -y
RUN micromamba create -y -n lorbin_env --file /tmp/lorbin-conda-linux-64.lock && \
    micromamba clean -a -y
RUN micromamba create -y -n bio --file /tmp/rosa-bio-linux-64.lock && \
    micromamba clean -a -y
RUN micromamba create -y -n cycloneseq-report --file /tmp/cycloneseq-report-template/conda-linux-64.lock && \
    micromamba clean -a -y

# Install LorBin from the vendored release package and expose it in the primary
# PATH used by WDL tasks.
COPY vendor/lorbin-0.1.0.tar.gz /tmp/lorbin-0.1.0.tar.gz
RUN /opt/conda/envs/lorbin_env/bin/pip install --no-cache-dir --no-deps /tmp/lorbin-0.1.0.tar.gz && \
    rm -f /tmp/lorbin-0.1.0.tar.gz && \
    ln -sf /opt/conda/envs/lorbin_env/bin/LorBin /opt/conda/envs/cycmetaasm/bin/LorBin

# Install Rosa from the vendored release wheel archive and expose it for the WDL
# QC tasks. The SHA256 matches the Process16S unified image asset.
COPY vendor/rosa-${ROSA_VERSION}.wheel.tar.gz /tmp/rosa.tar.gz
RUN echo "${ROSA_ARCHIVE_SHA256}  /tmp/rosa.tar.gz" | sha256sum -c - && \
    mkdir -p /tmp/rosa && \
    tar -xzf /tmp/rosa.tar.gz -C /tmp/rosa && \
    micromamba run -n bio python -m pip install --no-deps --no-cache-dir /tmp/rosa/rosa-*/*.whl && \
    rm -rf /tmp/rosa /tmp/rosa.tar.gz && \
    ln -sf /opt/conda/envs/bio/bin/rosa /usr/local/bin/rosa

# Install the shared CycloneSEQ report generator from the named BuildKit context.
RUN cd /tmp/cycloneseq-report-template && \
    micromamba run -n cycloneseq-report python -m pip install --no-build-isolation --no-cache-dir . && \
    rm -rf /tmp/cycloneseq-report-template && \
    ln -sf /opt/conda/envs/cycloneseq-report/bin/cycloneseq-report /usr/local/bin/cycloneseq-report

# Check the installation of Nextpolish, which may lose calgs.so in the shared libs
COPY src/lib/*.so /opt/conda/envs/cycmetaasm/share/nextpolish-1.4.1/lib/
ENV PATH=/usr/local/bin:/opt/conda/envs/cycmetaasm/bin:/opt/conda/envs/bio/bin:/opt/conda/envs/lorbin_env/bin:/opt/conda/envs/cycloneseq-report/bin:$PATH

# Ensure matplotlib uses a writable cache/config directory
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV XDG_CACHE_HOME=/tmp/.cache
RUN mkdir -p /tmp/matplotlib /tmp/.cache && chmod -R 777 /tmp/matplotlib /tmp/.cache

# ENV MAMBA_DOCKERFILE_ACTIVATE=1
# Fontconfig cache directory (writable)
RUN mkdir -p /var/cache/fontconfig && chmod -R 777 /var/cache/fontconfig
ENV FONTCONFIG_PATH=/etc/fonts
ENV FONTCONFIG_FILE=fonts.conf

# (Optional) pip mirror for CN network
# RUN python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Build the standalone binary once on your host:
#   pip install --upgrade pip nuitka
#   pip install -e .
# python -m nuitka \
#   --onefile \
#   --standalone \
#   --include-package=CycMetaAsm \
#   --include-package=plotly \
#   --include-package-data=plotly \
#   --output-dir=build \
#     src/CycMetaAsm
# Bring in the precompiled standalone cycmetaasm binary

COPY build/CycMetaAsm.bin /usr/local/bin/cycmetaasm
RUN chmod +x /usr/local/bin/cycmetaasm

# Default working directory for workflow runs
WORKDIR /data

# Default command for interactive checks; WDL tasks invoke specific tools.
CMD ["cycmetaasm", "--help"]
