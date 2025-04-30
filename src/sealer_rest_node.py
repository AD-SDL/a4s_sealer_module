"""REST-based node for A4S Sealer device"""

import datetime
import time
from pathlib import Path

from a4s_sealer_driver import A4S_SEALER_DRIVER
from fastapi.datastructures import State
from wei.modules.rest_module import RESTModule
from wei.types.module_types import ModuleState, ModuleStatus
from wei.types.step_types import ActionRequest, StepResponse, StepSucceeded
from wei.utils import extract_version

rest_module = RESTModule(
    name="sealer_node",
    version=extract_version(Path(__file__).parent.parent / "pyproject.toml"),
    description="A node to control the A4S Sealer device",
    model="A4S Sealer",
)
rest_module.arg_parser.add_argument(
    "--device",
    type=str,
    default="/dev/ttyUSB2",
    help="Serial device for communicating with the device",
)

rest_module.state.sealer = None


@rest_module.startup()
def sealer(state: State):
    """Sealer startup handler."""
    state.sealer = A4S_SEALER_DRIVER(state.device)
    print("Sealer online")


@rest_module.state_handler()
def state(state: State):
    """Returns the current state of the UR module"""
    if state.status not in [ModuleStatus.BUSY, ModuleStatus.ERROR, ModuleStatus.INIT, None] or (
        state.action_start and (datetime.datetime.now() - state.action_start > datetime.timedelta(0, 2))
    ):
        state.sealer.get_status()
        if state.sealer.status_msg == 3:
            state.status = ModuleStatus.ERROR
        elif state.sealer.status_msg == 0:
            state.status = ModuleStatus.IDLE

    return ModuleState(status=state.status, error="", status_msg=state.sealer.status_msg)


@rest_module.action(
    name="seal",
    description="Executes a sealing cycle on the Sealer device",
)
def seal(state: State, action: ActionRequest) -> StepResponse:
    """
    Seal a plate
    """
    state.sealer.seal()
    time.sleep(15)

    return StepSucceeded()


if __name__ == "__main__":
    rest_module.start()
