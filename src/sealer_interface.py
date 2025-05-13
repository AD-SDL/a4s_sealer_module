"""Python Driver for controlling the A4S Sealer instrument"""

import re
import time
from typing import Optional

import serial
from madsci.client.event_client import EventClient
from madsci.client.resource_client import ResourceClient
from madsci.common.types.resource_types import Resource


class Sealer:
    """
    Description:
                 - Python interface that allows remote commands to be executed using simple string messages over TCP/IP on PF400 cobot.
    Serial Communication Messages from the Robot:
                 - Responses begin with a "0" if the command was successful, or a negative error code number
    """

    def __init__(
        self,
        host_path: str = "/dev/ttyUSB2",
        baud_rate: int = 19200,
        resource_client: Optional[ResourceClient] = None,
        sealer_deck_resource: Optional[Resource] = None,
        seal_resource: Optional[Resource] = None,
        logger: Optional[EventClient] = None,
    ) -> "Sealer":
        """
        Initializes the Sealer class with the specified parameters.
        """

        self.host_path = host_path
        self.baud_rate = baud_rate
        self.resource_client = resource_client
        self.sealer_deck_resource = sealer_deck_resource
        self.seal_resource = seal_resource
        self.connection = None
        self.connect_sealer()
        self.sealer_output_msg = ""
        self.status_msg = ""
        self.heat = ""
        self.error_msg = ""
        self.logger = logger or EventClient()

    def connect_sealer(self) -> None:
        """
        Connect to serial port / If wrong port entered inform user
        """

        try:
            self.connection = serial.Serial(self.host_path, self.baud_rate)
        except Exception as e:
            raise Exception(
                "Could not establish connection, check that the device is connected and the correct USB serial device is selected."
            ) from e

    def disconnect(self) -> None:
        """
        Closes the serial connection to the device.
        """
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.logger.info("Serial connection closed.")
        else:
            self.logger.info("No open serial connection to close.")

    def get_status(self, time_wait: float = 500.0) -> str:
        """
        Records the data outputted by the Sealer and sets it to equal "" if no data is outputted in the provided time.
        """

        response_timer = time.time()
        while time.time() - response_timer < time_wait:
            if self.connection.in_waiting != 0:
                response = self.connection.read_until(expected=b"!")
                response_string = response.decode("utf-8")
                response_string_pat = re.search(
                    r"=\d+,(\d+),(\d+),\d+,\d+,\d+", response_string
                )
                if response_string_pat:
                    self.status_msg = int(response_string_pat[1])
                    self.heat = int(response_string_pat[2])
                break
            response_string = ""
        return response_string

    def send_command(self, command: str, timeout: float = 10.0) -> str:
        """Sends a serial command to the device and waits for a response."""

        self.sealer_output_msg = self.sealer_output_msg + "Command: " + command + "\n"

        self.connection.write(command.encode("utf-8"))

        ready_timer = time.time()
        response_buffer = ""
        while self.status_msg != 0:
            response_msg = self.get_status(timeout)
            self.logger.info(f"{self.status_msg=}")
            if response_msg != "":
                self.sealer_output_msg = self.sealer_output_msg + response_msg + "\n"

            response_buffer = response_buffer + response_msg

            if time.time() - ready_timer > 20:
                raise TimeoutError(f"Timed out during {command}.")

        return response_buffer

    def reset(self) -> None:
        """
        Clears error status/resets shuttle.
        """

        cmd_string = "*00SR=zz!"
        self.logger.info("Resetting Sealer")
        self.send_command(cmd_string)

    def open_gate(self) -> None:
        """
        Opens shuttle
        """

        cmd_string = "*00MO=zz!"
        self.logger.info("Opening Gate")
        self.send_command(cmd_string)

    def close_gate(self) -> None:
        """
        Closes shuttle
        """

        cmd_string = "*00MC=zz!"
        self.logger.info("Closing Gate")
        self.send_command(cmd_string)

    def set_temp(self, temp: int = 175) -> None:
        """
        Adjusts seal temperature to provided value.
        """

        temp = str(temp).zfill(4)
        cmd_string = f"*00DH={temp}zz!"
        self.logger.info(f"Setting Temp. to {temp}°C")
        self.send_command(cmd_string)

    def set_time(self, time: float = 3.0) -> None:
        """
        Adjusts seal time to the provided value.
        """

        time = str(int(time * 10)).zfill(4)
        cmd_string = f"*00DT={time}zz!"
        self.logger.info(f"Setting Seal Time to {time}s")
        self.send_command(cmd_string)

    def seal(self) -> None:
        """
        Conducts seal action.
        """

        cmd_string = "*00GS=zz!"
        self.logger.info("Sealing Plate")
        self.send_command(cmd_string)

        try:
            if self.resource_client and self.seal_resource:
                self.resource_client.increase_quantity(self.seal_resource, 1)
                if self.sealer_deck_resource:
                    plate_resource = self.sealer_deck_resource.children[0]
                    plate_resource.attributes["seal"] = self.seal_resource.resource_id
                    self.resource_client.update_resource(plate_resource)
        except Exception as e:
            self.logger.error(f"Error updating resources for sealer: {e}")

    def config_robot(self, temp: int, time: float = 3.0) -> None:
        """
        Sets the configuration for the robot, currently the seal time and temperature.
        """

        self.set_temp(temp)
        self.set_time(time)
