FROM ghcr.io/ad-sdl/madsci:v0.8.0

LABEL org.opencontainers.image.source=https://github.com/AD-SDL/a4s_sealer_module
LABEL org.opencontainers.image.description="Drivers and REST API's for the A4S Sealer"
LABEL org.opencontainers.image.licenses=MIT

#########################################
# Module specific logic goes below here #
#########################################

RUN mkdir -p a4s_sealer_module

COPY ./src a4s_sealer_module/src
COPY ./README.md a4s_sealer_module/README.md
COPY ./pyproject.toml a4s_sealer_module/pyproject.toml

RUN --mount=type=cache,target=/root/.cache \
    uv pip install --python ${MADSCI_VENV}/bin/python -e ./a4s_sealer_module

# Cross-distro serial access:
#   Ubuntu hosts: dialout = GID 20 (matches container's built-in `dialout` group).
#   Fedora hosts: dialout = GID 18 (added below as `dialout_fedora`).
# Baking both into the image means /dev/ttyUSB* works without compose-side
# `group_add` (which gets stripped by the madsci entrypoint's userdel/useradd).
RUN usermod -aG dialout madsci && \
    groupadd -g 18 dialout_fedora && \
    usermod -aG dialout_fedora madsci

CMD ["python", "a4s_sealer_module/src/sealer_rest_node.py"]

#########################################
