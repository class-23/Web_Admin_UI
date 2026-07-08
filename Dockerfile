FROM python:3.11-slim

# ========== 取消构建期系统代理（避免 apt/pip 走本地 clash 等代理）==========
ENV http_proxy=
ENV https_proxy=
ENV HTTP_PROXY=
ENV HTTPS_PROXY=
ENV no_proxy=*
ENV NO_PROXY=*
ENV all_proxy=
ENV ALL_PROXY=
# 同步禁用 pip 的代理
ENV PIP_NO_INSTALL_INDEX=0

# ========== 强制清空 apt / pip 的代理配置 ==========
# apt 不读环境变量，而是读 /etc/apt/apt.conf.d/*proxy* 配置文件。
# pip 不读环境变量，而是读 /etc/pip.conf 与 ~/.pip/pip.conf。
# 宿主机如果有 clash/proxy 等，会把代理配置 baked 进镜像，导致构建时无法联网。
RUN set -eux; \
    # ---- 1. apt 代理 ----
    find /etc/apt/apt.conf.d/ -type f \( -name '*proxy*' -o -name '*Proxy*' \) -delete 2>/dev/null || true; \
    printf 'Acquire::http::Proxy "false";\nAcquire::https::Proxy "false";\n' \
        > /etc/apt/apt.conf.d/99-disable-proxy.conf; \
    # ---- 2. pip 代理 ----
    find /etc -name 'pip.conf' -delete 2>/dev/null || true; \
    find /root -name 'pip.conf' -delete 2>/dev/null || true; \
    find /home -name 'pip.conf' -delete 2>/dev/null || true; \
    # 显式写一个"不使用代理" + 强制走阿里云 pypi 源 的 pip 配置
    # 注意：proxy 必须留空（proxy = 后面什么都不写），不能写 false，
    # 否则 pip 会把 "false" 当作代理 URL 去解析。
    mkdir -p /etc/pip; \
    printf '[global]\nproxy = \nindex-url = https://mirrors.aliyun.com/pypi/simple/\ntrusted-host = mirrors.aliyun.com\ntimeout = 60\n' \
        > /etc/pip.conf; \
    echo ">>> apt & pip proxy disabled"

# ========== apt 源改清华（Debian Trixie / bookworm 自动识别）==========
# 若 /etc/apt/sources.list.d/debian.sources 存在则改它（Trixie），
# 否则改 /etc/apt/sources.list（Bookworm）。
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' \
            /etc/apt/sources.list.d/debian.sources; \
      sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
            /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' \
            /etc/apt/sources.list; \
      sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
            /etc/apt/sources.list; \
    fi

# ========== 已有 libpq-dev / curl 就跳过 apt-get ==========
# 防止离线/代理不通时构建失败，也加速二次构建。
# libpq-dev 是 psycopg2 在 slim 镜像里的编译依赖；已装则可直接 pip install。
RUN set -eux; \
    NEED_INSTALL=0; \
    if ! dpkg -s libpq-dev >/dev/null 2>&1; then NEED_INSTALL=1; fi; \
    if ! dpkg -s curl      >/dev/null 2>&1; then NEED_INSTALL=1; fi; \
    if [ "$NEED_INSTALL" = "1" ]; then \
        echo ">>> Installing libpq-dev & curl via apt"; \
        apt-get update; \
        apt-get install -y --no-install-recommends libpq-dev curl; \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo ">>> libpq-dev & curl already installed, skipping apt-get"; \
    fi

WORKDIR /app

# ========== pip 依赖（清华源）==========
# 先复制 requirements.txt 单独成层，代码变更不会重装依赖
COPY requirements.txt .
# 在子 shell 中显式 unset 所有代理变量再调 pip，双保险
RUN set -eux; \
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY; \
    pip install --no-cache-dir -r requirements.txt \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        --timeout 60

# ========== 业务代码 ===========
COPY . .

# runtime 目录给 SQLite 配置库用
RUN mkdir -p runtime

EXPOSE 8082

CMD ["python", "main.py"]