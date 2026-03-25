# a4s_sealer_module

Implementation of a MADSci Node Module for integrating an A4S Plate Sealer.

## Installation and Usage

### Python

This project uses [PDM](https://pdm-project.org/en/latest/#installation) for dependency management.

```bash
# Install dependencies
pdm install
# Create a settings file (see Configuration below), then start the node
pdm run python -m sealer_rest_node
```

### Configuration

Settings are loaded automatically via MADSci's walk-up file discovery. Create a `node.settings.yaml` in your working directory (or any parent up to the `.madsci/` sentinel):

```yaml
node_name: a4s_sealer
node_url: http://0.0.0.0:2000
sealer_port: /dev/ttyUSB0
seal_time: 3.0
seal_temp: 175
```

All settings can also be provided as environment variables — see [`.env.example`](.env.example) for the full list. For detailed descriptions of every option, see [`docs/Configuration.md`](docs/Configuration.md). The node's stable ID is stored in `.madsci/registry.json` and reused across restarts.

### Docker

- We provide a `Dockerfile` and example docker compose file (`compose.yaml`) to run this node dockerized.
- There is also a pre-built image available as `ghcr.io/ad-sdl/a4s_sealer_module`.
- You can control the container user's id and group id by setting the `USER_ID` and `GROUP_ID` build args.
