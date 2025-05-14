"""REST-based node for A4S Sealer device"""

import time

from madsci.client.resource_client import ResourceClient
from madsci.common.types.action_types import ActionSucceeded
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.auth_types import OwnershipInfo
from madsci.common.types.base_types import Error
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types.definitions import (
    ContinuousConsumableResourceDefinition,
    SlotResourceDefinition,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from sealer_interface import Sealer


class SealerNodeConfig(RestNodeConfig):
    """Configuration for the UR node module."""

    device_path: str = "/dev/ttyUSB2"
    """Path to the device (e.g., /dev/ttyUSB0)."""


class SealerNode(RestNode):
    """A node to control the A4S Sealer device."""

    sealer_interface: Sealer = None
    config_model = SealerNodeConfig

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""

        if self.config.resource_server_url:
            self.resource_client = ResourceClient(self.config.resource_server_url)
            self.resource_owner = OwnershipInfo(node_id=self.node_definition.node_id)
            self.sealer_deck_resource = self.resource_client.init_resource(
                SlotResourceDefinition(
                    resource_name="sealer_deck",
                    owner=self.resource_owner,
                )
            )
            self.seal_resource = self.resource_client.init_resource(
                ContinuousConsumableResourceDefinition(
                    resource_name="seal",
                    owner=self.resource_owner,
                )
            )
        else:
            self.resource_client = None
            self.sealer_deck_resource = None
            self.seal_resource = None

        self.sealer_interface = Sealer(
            self.config.device_path,
            resource_client=self.resource_client,
            sealer_deck_resource=self.sealer_deck_resource,
            seal_resource=self.seal_resource,
            logger=self.logger,
        )

    def shutdown_handler(self) -> None:
        """Called to close connections to devices or clean up any other resources."""
        try:
            self.logger.log("Shutting down Sealer node...")
            if self.sealer_interface:
                self.sealer_interface.disconnect()
                self.logger.log("Sealer node closed!")
                self.shutdown_has_run = True
                del self.sealer_interface
                self.sealer_interface = None
            else:
                self.logger.log("Sealer node not initialized, nothing to close.")
        except Exception as err:
            self.logger.log_error(f"Error shutting down the Sealer Node: {err}")

    def state_handler(self) -> None:
        """Periodically checks the state of the Sealer device and updates the node's state."""
        if self.sealer_interface:
            self.sealer_interface.get_status()
        else:
            self.logger.log_error("Sealer interface is not initialized")
            return

        if self.sealer_interface.status_msg == 3:
            self.node_state = {
                "sealer_status_code": "ERROR",
            }
            self.logger.log_error("Sealer error")

        elif self.sealer_interface.status_msg == 0:
            self.node_state = {
                "sealer_status_code": "READY",
            }

    @action(name="seal", description="Seal a plate")
    def seal(self) -> ActionSucceeded:
        """Seal a plate"""
        self.sealer_interface.seal()
        time.sleep(15)
        return ActionSucceeded()

    def reset(self) -> AdminCommandResponse:
        """Reset the sealer and seal resource"""
        try:
            if (
                self.resource_client
                and self.sealer_deck_resource
                and self.seal_resource
            ):
                self.resource_client.empty(self.seal_resource)
            return super().reset()
        except Exception as e:
            self.logger.log_error(f"Error resetting the sealer: {e}")
            return AdminCommandResponse(success=False, errors=[Error.from_exception(e)])


if __name__ == "__main__":
    sealer_node = SealerNode()
    sealer_node.start_node()
