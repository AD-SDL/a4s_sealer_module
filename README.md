# A4S Sealer Module

A python driver and MADSci-compatible REST server for controlling and communicating with an A4S Sealer.

## User Guide

### Python Installation

```
git clone https://github.com/ad-sdl/a4s_sealer_module.git
cd a4s_sealer_module
python -m venv .venv && src .venv/bin/activate
pdm install
```

To run the MADSci REST node, create a node definition files using

```
madsci node create
```

Then use the following command to start the node

```
python -m a4s_sealer_rest_node 
```

### Docker Installation

After installing and configuring docker, run

```
git clone https://github.com/ad-sdl/a4s_sealer_module.git
cd a4s_sealer_module
docker compose build
docker compose up
```
