class CYLTekException(Exception):
    """Exception wrapping any communication errors with the device."""

class CYLTekDeviceUnavailableException(CYLTekException):
    """Exception raised when connect to cyl device fails.
    """

class CYLTekDeviceError(CYLTekException):
    """Exception communicating an error delivered by the target device.
    The device given error code and message can be accessed with  `code` and `message`
    variables.
    """

    def __init__(self, error):
        self.code = error.get("code")
        self.message = error.get("message")
