"""REST-based node for A4S Sealer device"""

from madsci.common.types.action_types import ActionFailed, ActionResult, ActionSucceeded
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types import DiscreteConsumable, Slot
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode
from pydantic import Field

from sealer_interface import Sealer


class SealerNodeConfig(RestNodeConfig):
    """Configuration for the UR node module."""

    device_path: str = "/dev/ttyUSB2"
    """Path to the device (e.g., /dev/ttyUSB0)."""
    seal_time: float = 3.0
    """Default sealing time in seconds."""
    seal_temp: int = Field(default=175, ge=50, le=200)
    """Default sealing temperature in Celsius."""
    adapter_block: str = Field(
        default="",  # TODO: Consult casey for list/default
        description="Name of the adapter block currently installed on the sealer",
    )


class SealerNode(RestNode):
    """A node to control the A4S Sealer device."""

    sealer: Sealer = None
    config: SealerNodeConfig = SealerNodeConfig()
    config_model = SealerNodeConfig
    module_version = "1.1.0"

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""

        self.create_resource_templates()
        self.create_resources()

        self.sealer = Sealer(
            self.config.device_path,
            resource_client=self.resource_client,
            nest=self.nest,
            seal_roll=self.seal_roll,
            logger=self.logger,
        )
        self.sealer.connect_sealer()
        if not self.sealer.connection.is_open:
            self.logger.log_error("Sealer connection failed")
            raise RuntimeError("Sealer connection failed")
        self.sealer.configure_instrument(
            temp=self.config.seal_temp, seal_time=self.config.seal_time
        )

    def create_resource_templates(self) -> None:
        """Handle creation of Sealer-specific resource templates"""

        self.resource_client.create_template(
            template_name="a4s_sealer_nest_template",
            description="Plate Nest for an a4s sealer",
            resource=Slot(resource_name="a4s_sealer_nest_template"),
            version="1.0.0",
        )
        self.resource_client.create_template(
            template_name="a4s_seal_roll_template",
            description="Plate seal roll used in an a4s sealer",
            resource=DiscreteConsumable(
                resource_name="a4s_seal_roll_template",
                quantity=1000,
                capacity=1000,
            ),
            version="1.1.0",
        )

    def create_resources(self) -> None:
        """Handle creating resources from templates on node startup"""

        self.nest = self.resource_client.create_resource_from_template(
            template_name="a4s_sealer_nest_template",
            resource_name=f"{self.node_info.node_name}.nest",
        )
        self.seal_roll = self.resource_client.create_resource_from_template(
            template_name="a4s_seal_roll_template",
            resource_name=f"{self.node_info.node_name}.seal_roll",
        )

    def shutdown_handler(self) -> None:
        """Called to close connections to devices or clean up any other resources."""
        try:
            if self.sealer:
                del self.sealer
                self.sealer = None
        except Exception as err:
            self.logger.log_error(f"Error shutting down the Sealer Node: {err}")

    def state_handler(self) -> None:
        """Periodically checks the state of the Sealer device and updates the node's state."""
        if self.sealer:
            self.node_state["sealer_interface_initialized"] = True
            self.sealer.read_messages()
            self.node_state["sealer_connected"] = self.sealer.connection.is_open
        else:
            self.node_state["sealer_interface_initialized"] = False
            self.node_state["sealer_connected"] = False
            self.logger.log_warning("Sealer interface is not initialized")
            return

        self.node_state["sealer_operation_status"] = (
            self.sealer.sealer_operation_status.model_dump(mode="json")
            if self.sealer.sealer_operation_status
            else None
        )
        self.node_state["sealer_system_status"] = (
            self.sealer.sealer_system_status.model_dump(mode="json")
            if self.sealer.sealer_system_status
            else None
        )
        self.node_state["sealer_command_accepted"] = (
            self.sealer.sealer_command_accepted.model_dump(mode="json")
            if self.sealer.sealer_command_accepted
            else None
        )
        self.node_state["sealer_command_rejected"] = (
            self.sealer.sealer_command_rejected.model_dump(mode="json")
            if self.sealer.sealer_command_rejected
            else None
        )
        self.node_state["sealer_communication_busy"] = (
            self.sealer.sealer_communication_busy.model_dump(mode="json")
            if self.sealer.sealer_communication_busy
            else None
        )

    @action(name="seal", description="Seal a plate")
    def seal(self) -> None:
        """Seal a plate"""
        self.sealer.seal()
        if self.sealer.sealer_system_status.error_code != 0:
            self.logger.log_error(
                f"Sealer error: {self.sealer.sealer_system_status.error_code}"
            )
            raise RuntimeError(
                f"Sealer error code: {self.sealer.sealer_system_status.error_code}",
            )

    @action(name="open", description="Open the sealer")
    def open(self) -> None:
        """Open the sealer"""
        self.sealer.open_gate()
        if self.sealer.sealer_system_status.error_code != 0:
            self.logger.log_error(
                f"Sealer error: {self.sealer.sealer_system_status.error_code}"
            )
            raise RuntimeError(
                f"Sealer error code: {self.sealer.sealer_system_status.error_code}",
            )

    @action(name="close", description="Close the sealer")
    def close(self) -> None:
        """Close the sealer"""
        self.sealer.close_gate()
        if self.sealer.sealer_system_status.error_code != 0:
            self.logger.log_error(
                f"Sealer error: {self.sealer.sealer_system_status.error_code}"
            )
            raise RuntimeError(
                f"Sealer error code: {self.sealer.sealer_system_status.error_code}",
            )

    @action(name="configure", description="Configure the sealer")
    def configure(self, seal_time: float, seal_temp: int) -> ActionResult:
        """Configure the sealer"""
        if seal_temp < 50 or seal_temp > 200:
            return ActionFailed(
                errors="Seal temperature must be between 50 and 200 degrees Celsius",
            )
        if seal_time < 0 or seal_time > 10:
            return ActionFailed(
                errors="Seal time must be greater than 0 seconds and less than 10 seconds",
            )
        self.sealer.configure_instrument(temp=seal_temp, seal_time=seal_time)
        if self.sealer.sealer_system_status.error_code != 0:
            self.logger.log_error(
                f"Sealer error: {self.sealer.sealer_system_status.error_code}"
            )
            raise RuntimeError(
                f"Sealer error code: {self.sealer.sealer_system_status.error_code}",
            )
        return ActionSucceeded()

    def reset(self) -> AdminCommandResponse:
        """Reset the sealer"""
        response = super().reset()
        self.sealer.reset()
        if self.sealer.sealer_system_status.error_code != 0:
            self.logger.log_error(
                f"Sealer error: {self.sealer.sealer_system_status.error_code}"
            )
            return AdminCommandResponse(
                success=False,
                errors=f"Sealer error code: {self.sealer.sealer_system_status.error_code}",
            )
        return response


if __name__ == "__main__":
    sealer_node = SealerNode()
    sealer_node.start_node()
