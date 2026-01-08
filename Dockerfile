# Build docker image for CycMetaAsm workflow
FROM mambaorg/micromamba:latest AS runtime

# Use Tsinghua mirrors for Debian/Ubuntu packages in the micromamba base
USER root
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
      ca-certificates \
      time \
      coreutils \
      wget \
      curl \
      && rm -rf /var/lib/apt/lists/*

# Try to use a pre-generated lock file

COPY conda-linux-64.lock /tmp/conda-linux-64.lock
RUN micromamba create -y -n cycmetaasm --file /tmp/conda-linux-64.lock && \
    micromamba clean -a -y
# Check the installation of Nextpolish, which may lose calgs.so in the shared libs
COPY src/lib/*.so /opt/conda/envs/cycmetaasm/share/nextpolish-1.4.1/lib/
ENV PATH=/opt/conda/envs/cycmetaasm/bin:$PATH

# Ensure matplotlib uses a writable cache/config directory
ENV MPLCONFIGDIR=/tmp/matplotlib
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

# Entrypoint: directly call the standalone cycmetaasm binary
# WDL engines can use this container to run steps that invoke this binary.
ENTRYPOINT ["/usr/local/bin/cycmetaasm"]
CMD ["--help"]
