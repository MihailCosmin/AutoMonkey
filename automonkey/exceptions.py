class AutoMonkeyNoAction(Exception):
    """
    AutoMonkey chain function will raise this Exception if no valid action exists
    in an automation step of the chain sequence.
    """
    def __init__(self, message):
        super().__init__(f"The provided action is not supported: {message}")


class AutoMonkeyNoTarget(Exception):
    """
    AutoMonkey chain function will raise this Exception if no valid target exists
    in an automation step of the chain sequence.
    """
    def __init__(self, message):
        super().__init__(f"The provided target is not supported: {message}")