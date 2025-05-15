"""Python Driver for controlling the A4S Sealer instrument"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import serial
from madsci.client.event_client import EventClient
from madsci.client.resource_client import ResourceClient
from madsci.common.types.resource_types import DiscreteConsumable, Slot

from sealer_messages import (
    SealerCommandAccepted,
    SealerCommandRejected,
    SealerCommunicationBusy,
    SealerOperationStatus,
    SealerSystemStatus,
    SystemStatus,
)


class Sealer:
    """
    Description:
                 - Python interface that allows remote commands to be executed using simple string messages over TCP/IP on PF400 cobot.
    Serial Communication Messages from the Robot:
                 - Responses begin with a "0" if the command was successful, or a negative error code number
    """

    resource_client: Optional[ResourceClient] = None
    sealer_plate_deck: Optional[Slot] = None
    seal_resource: Optional[DiscreteConsumable] = None

    connection: Optional[serial.Serial] = None
    serial_lock: threading.Lock = threading.Lock()
    action_lock: threading.Lock = threading.Lock()

    sealer_operation_status: Optional[SealerOperationStatus] = None
    sealer_system_status: Optional[SealerSystemStatus] = None
    sealer_command_accepted: Optional[SealerCommandAccepted] = None
    sealer_command_rejected: Optional[SealerCommandRejected] = None
    sealer_communication_busy: Optional[SealerCommunicationBusy] = None

    def __init__(
        self,
        serial_device: str = "/dev/ttyUSB2",
        baud_rate: int = 19200,
        resource_client: Optional[ResourceClient] = None,
        sealer_plate_deck: Optional[Slot] = None,
        seal_roll: Optional[DiscreteConsumable] = None,
        logger: Optional[EventClient] = None,
    ) -> "Sealer":
        """
        Initializes the Sealer class with the specified parameters.
        """

        self.serial_device = serial_device
        self.baud_rate = baud_rate
        self.resource_client = resource_client
        self.sealer_plate_deck = sealer_plate_deck
        self.seal_resource = seal_roll
        self.connection = None
        self.logger = logger or EventClient()

    def connect_sealer(self) -> None:
        """
        Connect to serial port / If wrong port entered inform user
        """

        self.connection = serial.Serial(self.serial_device, self.baud_rate, timeout=10)
        if self.connection.is_open:
            self.logger.info(
                f"Connected to {self.serial_device} at {self.baud_rate} baud."
            )
        else:
            raise ConnectionError(
                f"Failed to open serial port {self.serial_device}. Please check the connection."
            )

    def disconnect(self) -> None:
        """
        Closes the serial connection to the device.
        """
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.logger.info("Serial connection closed.")
        else:
            self.logger.info("No open serial connection to close.")

    def read_messages(self) -> None:
        """
        Reads messages from the serial port and store results.
        """
        if not self.connection or not self.connection.is_open:
            self.connect_sealer()

        with self.serial_lock:
            try:
                while self.connection.in_waiting > 0:
                    message = self.connection.read_until(b"!").decode("utf-8")
                    if message:
                        self.logger.log_debug(f"Received message: {message}")
                        self.process_message(message)
            except serial.SerialException as e:
                self.logger.error(f"Serial error: {e}")
            except Exception as e:
                self.logger.error(f"Error reading messages: {e}")

    def process_message(self, message: str) -> None:
        """Processes the received message and updates the appropriate status."""

        # *Remove everything in message before the first '*'
        star_index = message.find("*")
        if star_index != -1:
            message = message[star_index:]

        # Example: parse message type and update status objects
        if message.startswith("*"):
            if message[1] == "D":
                self.sealer_operation_status = SealerOperationStatus.from_string(
                    message
                )
            elif message[1] == "T":
                self.sealer_system_status = SealerSystemStatus.from_string(message)
            elif message[1] == "Y":
                self.sealer_command_accepted = SealerCommandAccepted.from_string(
                    message
                )
            elif message[1] == "N":
                self.sealer_command_rejected = SealerCommandRejected.from_string(
                    message
                )
            elif message[1] == "X":
                self.sealer_communication_busy = SealerCommunicationBusy.from_string(
                    message
                )
            else:
                self.logger.warning(f"Unrecognized message: {message}")
        else:
            self.logger.warning(f"Message does not start with '*': {message}")

    def send_command(self, command: str, timeout: float = 60.0) -> str:
        """Sends a serial command to the device and waits for a response."""

        if not self.connection or not self.connection.is_open:
            self.connect_sealer()

        with self.serial_lock:
            self.logger.log_debug(f"Sending command: {command}")
            action_send_time = datetime.now()
            self.connection.write(command.encode("utf-8"))

        accepted = False

        while True:
            self.logger.log_debug(f"Waiting for response to command: {command}")
            time.sleep(0.1)
            if datetime.now() - action_send_time > timedelta(seconds=timeout):
                raise TimeoutError("Timeout waiting for response from sealer.")
            self.read_messages()
            if (
                self.sealer_command_accepted
                and self.sealer_command_accepted.message_received > action_send_time
                and not accepted
            ):
                self.logger.info(f"Command {command} accepted")
                accepted = True
            if (
                self.sealer_command_rejected
                and self.sealer_command_rejected.message_received > action_send_time
            ):
                raise ValueError(f"Command {command} rejected")
            if (
                self.sealer_communication_busy
                and self.sealer_communication_busy.message_received > action_send_time
            ):
                raise ValueError(
                    f"Sealer is busy, command {command} cannot be executed"
                )
            if (
                self.sealer_system_status
                and self.sealer_system_status.message_received > action_send_time
            ):
                if self.sealer_system_status.status_msg in [
                    SystemStatus.FINISH,
                    SystemStatus.IDLE,
                ]:
                    self.logger.info(f"Command {command} executed successfully")
                    break
                if (
                    self.sealer_system_status.status_msg == SystemStatus.ERROR
                    or self.sealer_system_status.error_code != 0
                ):
                    raise ValueError(
                        f"Sealer error: {self.sealer_system_status.status_msg}"
                    )

    @staticmethod
    def create_sealer_command_str(
        command_code: str,
        parameter_str: str = "",
        command_index: int = 0,
        checksum: str = "zz",
    ) -> str:
        """
        Creates a command string to send to the sealer.

        Message Format:
            *<2-byte priority index><2-byte command>=<n byte parameters><2 byte Checksum>!
        Message Example:
            *00SR=zz!

        Index 00 means ignore command priority indexing, zz or ZZ means don't care about checksum.
        """

        if len(command_code) != 2:
            raise ValueError("Command code must be 2 characters long.")

        return (
            f"*{str(command_index).zfill(2)}{command_code}={parameter_str}{checksum}!"
        )

    def reset(self) -> None:
        """
        Reset the system status, error, and warning alarm.
        """
        with self.action_lock:
            self.logger.info("Resetting Sealer")
            self.send_command(self.create_sealer_command_str("SR"))

    def open_gate(self) -> None:
        """
        Ask the instrument to move the drawer forward to the outside position
        """

        with self.action_lock:
            self.logger.info("Opening Gate")
            self.send_command(self.create_sealer_command_str("MO"))

    def close_gate(self) -> None:
        """
        Ask the instrument to move the drawer backward to the inside position
        """

        with self.action_lock:
            self.logger.info("Closing Gate")
            self.send_command(self.create_sealer_command_str("MC"))

    def set_heating_block_temperature(self, temp: int = 175) -> None:
        """
        Set the sealing temperature of the instrument
        """

        if temp < 50 or temp > 200:
            raise ValueError("Temperature must be between 50 and 200 degrees Celsius.")

        with self.action_lock:
            self.logger.info(f"Setting Heating Block Temperature to {temp}°C")
            self.send_command(self.create_sealer_command_str("DH", str(temp).zfill(4)))

    def set_sealing_time(self, seconds: float = 3.0) -> None:
        """
        Adjusts seal time to the provided value.
        """

        time_str = str(int(seconds * 10)).zfill(4)
        with self.action_lock:
            self.logger.info(f"Setting Seal Time to {seconds} seconds")
            self.send_command(self.create_sealer_command_str("DT", time_str))

    def seal(self) -> None:
        """
        Ask the instrument to perform the sealing cycle
        """

        with self.action_lock:
            self.logger.info("Sealing Plate")
            self.send_command(self.create_sealer_command_str("GS"))

        try:
            if self.resource_client and self.seal_resource:
                self.sealer_plate_deck = self.resource_client.get_resource(
                    self.sealer_plate_deck.resource_id
                )
                self.resource_client.decrease_quantity(self.seal_resource, 1)
                if self.sealer_plate_deck and len(self.sealer_plate_deck.children) > 0:
                    plate_resource = self.sealer_plate_deck.children[0]
                    plate_resource.attributes["sealed"] = True
                    self.resource_client.update_resource(plate_resource)
        except Exception as e:
            self.logger.error(f"Error updating resources for sealer: {e}")

    def configure_instrument(self, temp: int, seal_time: float = 3.0) -> None:
        """
        Sets the configuration for the sealer, currently the seal time and temperature.
        """
        self.set_heating_block_temperature(temp)
        self.set_sealing_time(seal_time)
