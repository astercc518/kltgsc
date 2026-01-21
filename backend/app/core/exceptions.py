class AccountException(Exception):
    """Base exception for account related errors"""
    pass

class AccountFloodWaitException(AccountException):
    def __init__(self, wait_seconds: int, message: str = "FloodWait"):
        self.wait_seconds = wait_seconds
        self.message = message
        super().__init__(self.message)

class AccountBannedException(AccountException):
    pass

class AccountSpamBlockException(AccountException):
    pass

class AccountSessionInvalidException(AccountException):
    pass
