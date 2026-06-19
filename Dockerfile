# scan2telegram — Docker image (scanner + printer Telegram bot)
# Runs on any Linux host with network access to the HP MFP (e.g. Synology Container Manager).
FROM python:3.9-slim-bookworm

# System dependencies:
#  - SANE + HPLIP: network scanning via the hpaio backend
#  - CUPS (+ cups-filters): printing via the hpcups driver
#  - dbus: required by the hpaio backend (it aborts without a system bus)
#  - gnupg: required by hp-plugin to verify the proprietary plugin
#  - libreoffice-writer: DOCX/DOC -> PDF conversion before printing
RUN apt-get update && apt-get install -y --no-install-recommends \
    sane-utils libsane1 libsane-common libsane-dev libsane-hpaio \
    hplip cups cups-client cups-bsd cups-filters dbus \
    gnupg wget \
    libreoffice-writer \
    python3-dev gcc \
    libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev \
    liblcms2-dev libopenjp2-7-dev libtiff5-dev libffi-dev \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# HP proprietary plugin — host-based MFPs (e.g. M177fw) require it for BOTH scan and print.
# Pulled from HP at build time; the build fails if the plugin does not register.
RUN /bin/bash -c '{ echo d; yes; } | hp-plugin -i; grep -q "installed = 1" /var/lib/hp/hplip.state'

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/scans && chmod 755 /app/scans && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
