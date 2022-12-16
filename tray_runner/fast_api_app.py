"""
tray_runner.fast_api_app module.
"""
from datetime import timedelta
import logging
import os
import secrets
from functools import partial
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException
from pydantic import BaseModel

import tray_runner
from tray_runner import DEFAULT_CONFIG_FILE
from tray_runner.base_app import AppUser, BaseApp, DummyApp
from tray_runner.common_utils.common import copy_fields, get_languages, remove_app_menu_shortcut
from tray_runner.config import Config, ConfigCommand, ConfigCommandExecutionStatus, ConfigCommandInput, ConfigCommandScheduleMode
from tray_runner.constants import APP_NAME
from tray_runner.execution_manager import BaseExecutionManager, ExecutionManager
from tray_runner.gui.utils import create_tray_runner_app_menu_launcher, create_tray_runner_autostart_shortcut

LOG = logging.getLogger(__name__)


class LoginData(BaseModel):
    """
    Class that represents the data being sent for login process.
    """
    token: str


def create_app(base_app: BaseApp, execution_manager: BaseExecutionManager, secret_key: Optional[str] = None, auto_login_random: Optional[bool] = None) -> FastAPI:  # pylint: disable=too-many-statements,too-many-locals
    """
    Creates the FastAPI application.
    """

    if auto_login_random is None:
        auto_login_random = True

    api_app = FastAPI()
    if secret_key is None:
        secret_key = secrets.token_urlsafe(32)
    login_manager = LoginManager(secret_key, "/login")

    @login_manager.user_loader()
    def query_user(user_id: str):
        return base_app.get_user(user_id)

    @api_app.get("/ping")
    def ping():
        return {"ping": "pong"}

    @api_app.post("/auth/login")
    def auth_login(login_data: LoginData):
        user = base_app.verify_token(login_data.token)
        if not user:
            env_login_token = os.getenv("TRAY_RUNNER_LOGIN_TOKEN")
            if env_login_token and login_data.token == env_login_token:
                user = base_app.dummy_user
        if not user:
            raise InvalidCredentialsException

        access_token = login_manager.create_access_token(
            data= {"sub": user.get_id()},
            expires=timedelta(hours=12)
        )
        return {"access_token": access_token}

    @api_app.post("/auth/refresh")
    def auth_refresh(user: AppUser = Depends(login_manager)):
        raise NotImplementedError()
        return user

    @api_app.get("/auth/me")
    def auth_me(user: AppUser = Depends(login_manager)):
        return user

    @api_app.get("/commands", response_model=List[ConfigCommand])
    def commands_list(user: AppUser = Depends(login_manager)):
        return base_app.config.commands

    @api_app.put("/commands", response_model=ConfigCommand)
    def commands_create(command: ConfigCommandInput, user: AppUser = Depends(login_manager)):

        full_command = ConfigCommand(**command.dict())
        # Check for duplicated id
        if base_app.config.get_command_by_id(full_command.id):
            raise RuntimeError(f"Duplicated ID {full_command.id}")

        base_app.config.commands.append(full_command)
        base_app.config.save()
        return full_command

    @api_app.get("/commands/{command_id}", response_model=ConfigCommand)
    def commands_get(command_id: str, user: AppUser = Depends(login_manager)) -> ConfigCommand:
        command = base_app.config.get_command_by_id(command_id)
        if not command:
            raise HTTPException(status_code=404, detail="Item not found")
        return command

    @api_app.post("/commands/{command_id}", response_model=ConfigCommand)
    def commands_update(command_id: str, command: ConfigCommandInput, user: AppUser = Depends(login_manager)):

        dst_command = base_app.config.get_command_by_id(command_id)
        if not dst_command:
            raise HTTPException(status_code=404, detail="Item not found")

        # Check for duplicated id
        for command in base_app.config.commands:
            # Skip self command
            if command.id != command_id:
                # Check if id is already being used
                if command.id == dst_command.id:
                    raise RuntimeError(f"Duplicated ID {dst_command.id}")

        copy_fields(command, dst_command)
        base_app.config.save()
        return dst_command

    @api_app.delete("/commands/{command_id}", response_model=ConfigCommand)
    def commands_delete(command_id: str, user: AppUser = Depends(login_manager)):

        command = base_app.config.get_command_by_id(command_id)
        if not command:
            raise HTTPException(status_code=404, detail="Item not found")

        execution_manager.stop_command_thread(command)
        base_app.config.commands.remove(command)
        base_app.config.save()
        return command

    app = FastAPI()
    app.mount("/api", api_app)
    app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp"), html=True), name="static")

    return app


def run_app():
    """
    Method that is called when running from `uvicorn`.
    """

    logging.getLogger("tray_runner").setLevel(logging.DEBUG)
    config = Config.load_from_file(DEFAULT_CONFIG_FILE)
    dummy_app = DummyApp(config=config)
    execution_manager = ExecutionManager(dummy_app)
    secret_key = os.getenv("TRAY_RUNNER_SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_urlsafe(32)
    return create_app(dummy_app, execution_manager, secret_key=secret_key, auto_login_random=True)
