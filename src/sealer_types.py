"""Data Models for Sealer Messages and other Types/Models"""

from datetime import datetime, time
from enum import Enum
from typing import Optional

from madsci.common.ownership import get_current_ownership_info
from madsci.common.types.auth_types import OwnershipInfo
from pydantic import BaseModel, Field


class SealInfo(BaseModel):
    """Seal Metadata to store on sealed resources"""

    sealed: bool = True
    """Whether the plate is sealed or not"""
    sealed_by: OwnershipInfo = Field(default_factory=get_current_ownership_info)
    """Ownership info for the sealer used to seal the plate"""
    seal_roll_id: Optional[str]
    """Resource ID of the seal roll used to seal the plate"""
    seal_time: datetime = Field(default_factory=datetime.astimezone())
    """A datetime stamp when the seal was performed (approximate)"""


class SystemStatus(Enum):
    """System status codes for the sealer."""

    IDLE = 0
    """The system is idle."""
    SINGLE_CYCLE = 1
    """The system is running a single cycle."""
    REPEAT_CYCLE = 2
    """The system is running a repeat cycle."""
    ERROR = 3
    """The system is in an error state."""
    FINISH = 4
    """The system has finished its operation."""


class HeatingBlockStatus(Enum):
    """Heating block status codes for the sealer."""

    HEATER_OFF = 0
    """The heating block is off."""
    READY = 1
    """The heating block is ready."""
    HEATING = 2
    """The heating block is heating up."""
    COOLING = 3
    """The heating block is cooling down."""
    CONVERGING = 4
    """The heating block is converging to the target temperature."""


class SealerOperationStatus(BaseModel):
    """
    Model for the sealer operation status message.

    Message Format:
        *D<firmware_version>=<running_time>,<sealing_cycles><2 byte Checksum>!
    Message Example:
        *D515A=0051315529,0000000432EE!
    """

    firmware_version: str
    """The firmware version of the device."""
    running_time: int
    """The time the sealer has been running in seconds."""
    sealing_cycles: int
    """The number of sealing cycles completed."""
    message_received: Optional[datetime] = Field(
        default_factory=datetime.now, description="The time the message was received."
    )

    @classmethod
    def from_string(cls, message: str) -> "SealerOperationStatus":
        """
        Parses the message string and sets the attributes of the class.
        """
        if not message.startswith("*D"):
            raise ValueError("Invalid message format, no *D prefix")
        if not message.endswith("!"):
            raise ValueError("Invalid message format, no terminal ! character")

        # Extract the relevant part of the message
        firmware_version, parameters = message[2:-3].split("=")

        running_time, sealing_cycles = map(int, parameters.split(","))
        return cls(
            firmware_version=firmware_version,
            running_time=running_time,
            sealing_cycles=sealing_cycles,
        )


class SealerSystemStatus(BaseModel):
    """Model for the sealer system status message.

    Message Format:
        *T<timestamp>=<current_temp>,<status_msg>,<heating_status>,<error_code>,<warning_message_code>,<sensor_status_code>,<countdown_sealing_time><2 byte Checksum>!

    Message Example:
        *T07:11:30=1697,1,2,0,0,0,300FM!

    """

    timestamp: time
    """The time of the message, reported by the device."""
    current_temp: float
    """The current temperature of the device in degrees Celsius. Reported by device in integer tenths of degrees Celsius * 10, we normalize."""
    status_msg: SystemStatus
    """The status of the device."""
    heating_status: HeatingBlockStatus
    """The status of the heating block."""
    error_code: int
    """The error code, if any. 0 means no error."""
    warning_message_code: int
    """The warning message code, if any. 0 means no warning."""
    sensor_status_code: int = Field(ge=0, le=255)
    """The status byte of the sensor."""
    countdown_sealing_time: int
    """The countdown time for sealing in seconds."""

    # * Bits 0-7 from Sensor Status Byte
    shuttle_middle_sensor: bool
    """True if the middle sensor is triggered."""
    shuttle_open_sensor: bool
    """True if the open sensor is triggered."""
    shuttle_closed_sensor: bool
    """True if the closed sensor is triggered."""
    clean_door_sensor: bool
    """True if the clean door sensor is triggered."""
    seal_roll_sensor: bool
    """True if the seal roll sensor is triggered."""
    heater_motor_up_sensor: bool
    """True if the heater motor up sensor is triggered."""
    heater_motor_down_sensor: bool
    """True if the heater motor down sensor is triggered."""
    no_connect: bool
    """Reserved for future use."""
    message_received: Optional[datetime] = Field(
        default_factory=datetime.now, description="The time the message was received."
    )

    @classmethod
    def from_string(cls, message: str) -> "SealerSystemStatus":
        """
        Parses the message string and sets the attributes of the class.
        """
        if not message.startswith("*T"):
            raise ValueError("Invalid message format, no *T prefix")
        if not message.endswith("!"):
            raise ValueError("Invalid message format, no terminal ! character")

        # Extract the relevant part of the message
        message = message[2:-3]  # Remove the *T prefix and the <checksum>! suffix

        # Extract the timestamp
        timestamp_str, parameter_bytes = message.split("=")
        timestamp = time.fromisoformat(timestamp_str)

        # Extract the rest of the fields
        (
            current_temp,
            status_msg,
            heating_status,
            error_code,
            warning_message_code,
            sensor_status_code,
            countdown_sealing_time,
        ) = map(int, parameter_bytes.split(","))

        # Extract sensor status bits
        shuttle_middle_sensor = bool(sensor_status_code & 0b00000001)
        shuttle_open_sensor = bool(sensor_status_code & 0b00000010)
        shuttle_closed_sensor = bool(sensor_status_code & 0b00000100)
        clean_door_sensor = bool(sensor_status_code & 0b00001000)
        seal_roll_sensor = bool(sensor_status_code & 0b00010000)
        heater_motor_up_sensor = bool(sensor_status_code & 0b00100000)
        heater_motor_down_sensor = bool(sensor_status_code & 0b01000000)
        no_connect = bool(sensor_status_code & 0b10000000)

        return cls(
            timestamp=timestamp,
            current_temp=float(current_temp) / 10,
            status_msg=SystemStatus(status_msg),
            heating_status=HeatingBlockStatus(heating_status),
            error_code=error_code,
            warning_message_code=warning_message_code,
            sensor_status_code=sensor_status_code,
            countdown_sealing_time=countdown_sealing_time,
            shuttle_middle_sensor=shuttle_middle_sensor,
            shuttle_open_sensor=shuttle_open_sensor,
            shuttle_closed_sensor=shuttle_closed_sensor,
            clean_door_sensor=clean_door_sensor,
            seal_roll_sensor=seal_roll_sensor,
            heater_motor_up_sensor=heater_motor_up_sensor,
            heater_motor_down_sensor=heater_motor_down_sensor,
            no_connect=no_connect,
        )


class SealerCommandAccepted(BaseModel):
    """
    Model for the sealer command accepted message.

    Message Format:
        *Y<command_index><2 byte Checksum>!

    Message Example:
        *Y01PL!
    """

    command_index: int
    """The index of the command that was accepted."""
    message_received: Optional[datetime] = Field(
        default_factory=datetime.now, description="The time the message was received."
    )

    @classmethod
    def from_string(cls, message: str) -> "SealerCommandAccepted":
        """
        Parses the message string and sets the attributes of the class.
        """
        if not message.startswith("*Y"):
            raise ValueError("Invalid message format, no *Y prefix")
        if not message.endswith("!"):
            raise ValueError("Invalid message format, no terminal ! character")

        # Extract the relevant part of the message
        command_index = int(message[2:-3])
        return cls(command_index=command_index)


class SealerCommandRejected(BaseModel):
    """
    Model for the sealer command rejected message.

    Message Format:
        *N<2 byte command_index><2 byte Checksum>!

    Message Example:
        *N010G!
    """

    command_index: int
    """The index of the command that was rejected."""
    message_received: Optional[datetime] = Field(
        default_factory=datetime.now, description="The time the message was received."
    )

    @classmethod
    def from_string(cls, message: str) -> "SealerCommandRejected":
        """
        Parses the message string and sets the attributes of the class.
        """
        if not message.startswith("*N"):
            raise ValueError("Invalid message format, no *N prefix")
        if not message.endswith("!"):
            raise ValueError("Invalid message format, no terminal ! character")

        # Extract the relevant part of the message
        command_index = int(message[2:-3])
        return cls(command_index=command_index)


class SealerCommunicationBusy(BaseModel):
    """
    Model for the sealer communication busy message, indicating that the device is busy and cannot accept commands.

    Message Format:
        *X<2 byte command_index><2 byte Checksum>!

    Message Example:
        *X01PL!
    """

    command_index: int
    """The index of the command that was busy."""
    message_received: Optional[datetime] = Field(
        default_factory=datetime.now, description="The time the message was received."
    )

    @classmethod
    def from_string(cls, message: str) -> "SealerCommunicationBusy":
        """
        Parses the message string and sets the attributes of the class.
        """
        if not message.startswith("*X"):
            raise ValueError("Invalid message format, no *X prefix")
        if not message.endswith("!"):
            raise ValueError("Invalid message format, no terminal ! character")

        # Extract the relevant part of the message
        command_index = int(message[2:-3])
        return cls(command_index=command_index)
