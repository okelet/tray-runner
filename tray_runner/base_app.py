"""
tray_runner.base_app module.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field

import tray_runner
from tray_runner import DEFAULT_CONFIG_FILE
from tray_runner.config import Config
from tray_runner.constants import APP_ID, APP_NAME
from tray_runner.version_checker import VersionChecker


class AppUser(BaseModel):
    """
    Class that represents a virtual application user, just to make login process work.
    """

    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_active: bool = True
    is_authenticated: bool = True
    is_anonymous: bool = False

    def get_id(self):
        """
        Returns the ID of the user.
        """
        return self.user_id


class LoginToken(BaseModel):
    """
    Class that represents a login token, with a value and an expiration.
    """

    value: str = Field(default_factory=lambda: str(uuid.uuid4()))
    expiration: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=1))


class BaseApp:
    """
    Base class that defines the methods that must be implemented by child classes.
    """

    def __init__(self, config: Config):
        self.config = config
        self.tokens: List[LoginToken] = []
        self.dummy_user = AppUser(user_id=str(uuid.UUID(int=0)))
        self.version_checker = VersionChecker(app_name=APP_ID, current_version=tray_runner.__version__, check_interval_seconds=self.config.app_version_check_interval_seconds)

    def add_token(self) -> LoginToken:
        token = LoginToken()
        self.tokens.append(token)
        return token

    def verify_token(self, token_secret: str) -> Optional[AppUser]:

        found_token: Optional[LoginToken] = None
        for token_data in self.tokens:
            if token_data.value == token_secret:
                found_token = token_data
                break

        if not found_token:
            return None

        if found_token.expiration < datetime.utcnow():
            return None

        return self.dummy_user

    def get_user(self, user_id: str) -> Optional[AppUser]:
        if self.dummy_user.get_id() == user_id:
            return self.dummy_user
        return None

    def send_notification(self, title: str, message: str) -> None:
        """
        Sends a notification.
        """
        raise NotImplementedError()

    def on_status_changed(self) -> None:
        """
        Called by CommandThread class when the status of a command has changed, so, for example, the menu can be updated.
        """
        raise NotImplementedError()



class DummyApp(BaseApp):
    """
    Dummy class that implements the methods needed to run the web application.
    """

    def __init__(self, config: Config):
        """
        Class constructor.
        """
        super().__init__(config)

    def send_notification(self, title: str, message: str) -> None:
        """
        Sends a notification.
        """
        print(f"Received notification -> title: {title}, message: {message}")

    def on_status_changed(self) -> None:
        """
        Called by CommandThread class when the status of a command has changed, so, for example, the menu can be updated.
        """
        print("Received status_changed event")
