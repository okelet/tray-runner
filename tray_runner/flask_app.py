"""
tray_runner.flask_app module.
"""
import logging
import secrets
from datetime import datetime
from functools import partial
from http import HTTPStatus
from typing import Any, Dict, Optional

from babel import Locale
from babel.util import get_localzone
from flask import Flask, flash, has_request_context, jsonify, make_response, redirect, render_template, request, url_for
from flask_babel import Babel, get_locale, get_timezone, gettext
from flask_bootstrap import Bootstrap4
from flask_login import LoginManager, login_required, login_user
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

import tray_runner
from tray_runner import DEFAULT_CONFIG_FILE
from tray_runner.base_app import BaseApp, DummyApp
from tray_runner.common_utils.common import get_languages, remove_app_menu_shortcut
from tray_runner.config import Config, ConfigCommand, ConfigCommandExecutionStatus, ConfigCommandScheduleMode
from tray_runner.constants import APP_NAME
from tray_runner.execution_manager import BaseExecutionManager, ExecutionManager
from tray_runner.flask_forms import CommandForm, SettingsForm, command_id_validator
from tray_runner.gui.utils import create_tray_runner_app_menu_launcher, create_tray_runner_autostart_shortcut

LOG = logging.getLogger(__name__)


def create_app(base_app: BaseApp, execution_manager: BaseExecutionManager, disable_flask_logs: Optional[bool] = None, auto_login_random: Optional[bool] = None) -> Flask:  # pylint: disable=too-many-statements,too-many-locals
    """
    Creates the Flask application.
    """

    if disable_flask_logs is None:
        disable_flask_logs = True

    if auto_login_random is None:
        auto_login_random = True

    app = Flask(__name__)
    app.config.from_mapping(
        **dict(
            LANGUAGES=["en_US", "es_ES"],
            DEBUG_TB_INTERCEPT_REDIRECTS=False,
        )
    )
    app.secret_key = secrets.token_urlsafe(32)

    if disable_flask_logs:
        LOG.debug("Removing Flask default handler...")
        from flask.logging import default_handler  # pylint: disable=import-outside-toplevel

        app.logger.removeHandler(default_handler)

    _toolbar = None
    if app.debug:
        app.templates_auto_reload = True
        app.logger.setLevel(logging.DEBUG)
        try:

            # Init debug toolbar
            from flask_debugtoolbar import DebugToolbarExtension  # pylint: disable=import-outside-toplevel

            _toolbar = DebugToolbarExtension(app)

            # Disable SQLAlchemy panel (we don't use it)
            new_panels = list(app.config["DEBUG_TB_PANELS"])
            new_panels.remove("flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel")
            app.config["DEBUG_TB_PANELS"] = tuple(new_panels)

        except ImportError as ex:
            LOG.warning("Error initializing DebugToolbar: %s.", str(ex))

    babel = Babel(app)
    _bootstrap = Bootstrap4(app)
    login_manager = LoginManager(app)

    if auto_login_random:

        @login_manager.unauthorized_handler
        def unauthorized():
            return redirect(url_for("login", token=base_app.add_token().value, back_to=request.full_path))

    @login_manager.user_loader
    def load_user(user_id):
        return base_app.get_user(user_id)

    @babel.localeselector
    def babel_locale_selector():
        request_locale = request.values.get("locale").lower() if request.values.get("locale") else None
        if request_locale:
            return parse_accept_header(request_locale, LanguageAccept).best_match(app.config["LANGUAGES"])
        return request.accept_languages.best_match(app.config["LANGUAGES"])

    @babel.timezoneselector
    def babel_timezone_selector():
        return get_localzone()

    @app.before_request
    def before_request_func():
        new_tokens = []
        for token in base_app.tokens:
            if token.expiration > datetime.utcnow():
                new_tokens.append(token)
        base_app.tokens = new_tokens

    @app.context_processor
    def inject_common_vars():

        language = str(get_locale())
        simple_language = ""
        if language:
            simple_language = language.split("_", maxsplit=1)[0]

        return dict(
            debug=app.debug,
            language=language,
            dashLanguage=language.replace("_", "-"),
            simpleLanguage=simple_language,
            languageSet=bool(base_app.config.language),
            timezone=str(get_timezone()),
            current_version=tray_runner.__version__,
            remote_version=base_app.version_checker.remote_version,
        )

    @app.url_defaults
    def add_language_code(endpoint: str, values: Dict[str, Any]):

        if not endpoint.startswith("_debug_toolbar") and endpoint != "static" and has_request_context():

            forced_locale = request.values.get("locale")
            if forced_locale:
                values["locale"] = forced_locale

            if app.env == "development":
                forced_user = request.args.get("_impersonate")
                if forced_user:
                    values["_impersonate"] = forced_user

    @app.route("/")
    @login_required
    def home():
        return render_template(
            "home.html",
            total_runs=base_app.config.app_runs,
            command_runs=sum(x.total_runs for x in base_app.config.commands),
            all_commands=base_app.config.commands,
            commands_with_errors=[x for x in base_app.config.commands if x.total_runs > 0 and x.last_status and x.last_status in [ConfigCommandExecutionStatus.FAILED, ConfigCommandExecutionStatus.ERROR]],
            running_jobs=execution_manager.get_running_jobs(),
        )

    @app.route("/login")
    def login():

        token_secret = request.args.get("token")
        if not token_secret:
            return "Missing login token", HTTPStatus.BAD_REQUEST

        user = base_app.verify_token(token_secret)
        if not user:
            return "Invalid login token", HTTPStatus.BAD_REQUEST

        login_user(user)

        flash(gettext("Login successful"), "success")
        back_to = request.args.get("back_to")
        if back_to:
            return redirect(back_to)
        return redirect(url_for("home"))

    @app.route("/commands", methods=["GET"])
    @login_required
    def commands_list():
        export_format = request.args.get("export")
        if export_format:
            if export_format == "json":
                r = make_response(base_app.config.json(exclude_defaults=True, exclude_none=True, indent=2))
                r.mimetype = "application/json"
                return r
            return f"Format {export_format} not supported.", HTTPStatus.UNPROCESSABLE_ENTITY
        return render_template(
            "commands_list.html",
            commands=base_app.config.commands,
        )

    @app.route("/commands/show/<command_id>", methods=["GET"])
    @login_required
    def commands_show(command_id: str):

        command = base_app.config.get_command_by_id(command_id)
        if not command:
            return "Command not found", HTTPStatus.NOT_FOUND

        export_format = request.args.get("export")
        if export_format:
            if export_format == "json":
                response = make_response(command.json(exclude_defaults=True, exclude_none=True, indent=2))
                response.mimetype = "application/json"
                return response
            return f"Format {export_format} not supported.", HTTPStatus.UNPROCESSABLE_ENTITY

        return render_template(
            "commands_show.html",
            config=base_app.config,
            command=command,
        )

    @app.route("/commands/logs/<command_id>", methods=["GET"])
    @login_required
    def commands_logs(command_id: str):

        command = base_app.config.get_command_by_id(command_id)
        if not command:
            return "Command not found", HTTPStatus.NOT_FOUND

        export_format = request.args.get("export")
        if export_format:
            if export_format == "json":
                r = make_response(command.get_logs().json(exclude_defaults=True, exclude_none=True, indent=2))
                r.mimetype = "application/json"
                return r
            return f"Format {export_format} not supported.", HTTPStatus.UNPROCESSABLE_ENTITY

        return render_template(
            "commands_logs.html",
            command=command,
            logs=command.get_logs().items,
        )

    @app.route("/commands/run/<command_id>", methods=["POST"])
    @login_required
    def commands_run(command_id: str):

        command = base_app.config.get_command_by_id(command_id)
        if not command:
            return "Command not found", HTTPStatus.NOT_FOUND

        execution_manager.start_command(command)

        flash(gettext("Command queued"), "info")
        return redirect(url_for("commands_logs", command_id=command.id))

    @app.route("/commands/delete/<command_id>", methods=["POST"])
    @login_required
    def commands_delete(command_id: str):

        command = base_app.config.get_command_by_id(command_id)
        if not command:
            return "Command not found", HTTPStatus.NOT_FOUND

        execution_manager.stop_command_thread(command)
        base_app.config.commands.remove(command)
        base_app.config.save()

        flash(gettext("Command deleted"), "info")
        return redirect(url_for("commands_list"))

    @app.route("/commands/add", methods=["GET", "POST"])
    @app.route("/commands/edit/<command_id>", methods=["GET", "POST"])
    @login_required
    def commands_edit(command_id: Optional[str] = None):

        is_new = False
        if command_id:
            command = base_app.config.get_command_by_id(command_id)
            if not command:
                return "Command not found", HTTPStatus.NOT_FOUND
        else:
            is_new = True
            command = ConfigCommand(id="", name="")

        form = CommandForm(obj=command)
        command_id_validator_partial = partial(command_id_validator, base_app.config, command)

        if request.args.get("validate") == "1":

            errors = []
            form.validate(extra_validators={"id": [command_id_validator_partial]})
            for field_name, error_messages in form.errors.items():
                field_id = None
                field_label = None
                if field_name is None:
                    field_name = "_"
                else:
                    field_name = form[field_name].name
                    field_id = form[field_name].id
                    field_label = form[field_name].label.text
                field_errors = []
                for err in error_messages:
                    field_errors.append(err)
                if field_errors:
                    errors.append({"field_name": field_name, "field_id": field_id, "field_label": field_label, "messages": field_errors})

            return jsonify({"errors": errors})

        # validate_on_submit can't be used because extra_validators is not allowed
        if form.is_submitted() and form.validate(extra_validators={"id": [command_id_validator_partial]}):
            form.populate_obj(command)
            if is_new:
                base_app.config.commands.append(command)
            if command.schedule_mode in [ConfigCommandScheduleMode.PERIOD, ConfigCommandScheduleMode.CRON]:
                command.next_run_dt = command.get_next_execution_dt()
            base_app.config.save()
            execution_manager.ensure_command_status(command)
            if is_new:
                flash(gettext("Command created"), "info")
            else:
                flash(gettext("Command updated"), "info")
            return redirect(url_for("commands_show", command_id=command.id))

        return render_template(
            "commands_edit.html",
            is_new=is_new,
            command=command,
            form=form,
        )

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        """
        Action to update the settings.
        """
        form = SettingsForm(obj=base_app.config)
        form.language.choices = get_languages(get_locale(), app.config["LANGUAGES"])

        if request.args.get("validate") == "1":

            errors = []
            form.validate()
            for field_name, error_messages in form.errors.items():
                if field_name is None:
                    field_name = "_"
                field_errors = []
                for err in error_messages:
                    field_errors.append(err)
                if field_errors:
                    errors.append({"field": field_name, "messages": field_errors})

            return jsonify({"errors": errors})

        if form.validate_on_submit():

            # Save config
            form.populate_obj(base_app.config)
            base_app.config.save()

            # Apply changes
            logging.getLogger(tray_runner.__name__).setLevel(str(base_app.config.log_level.value))
            if base_app.config.auto_start:
                create_tray_runner_autostart_shortcut()
            else:
                remove_app_menu_shortcut(APP_NAME, autostart=True)
            if base_app.config.create_app_menu_shortcut:
                create_tray_runner_app_menu_launcher()
            else:
                remove_app_menu_shortcut(APP_NAME)

            # Redirect
            flash(gettext("Settings updated"), "info")
            return redirect(url_for("settings"))

        return render_template(
            "settings.html",
            form=form,
        )

    @app.route("/save_language", methods=["POST"])
    @login_required
    def save_language():
        """
        Action to save the language from an AJAX request.
        """
        language = request.form.get("language")
        if language:

            language = language.replace("-", "_")
            if language not in app.config["LANGUAGES"]:
                return jsonify({"message": gettext("Invalid language")}), HTTPStatus.BAD_REQUEST

            base_app.config.language = language
            base_app.config.save()
            message = gettext(
                """Your language has been automatically set to {language}; you can change it in your <a href="{url}">settings</a>.""".format(  # pylint: disable=consider-using-f-string
                    language=Locale(language).languages[language],
                    url=url_for("settings"),
                )
            )
            return jsonify({"message": message})

        return jsonify({"message": gettext("Empty language")}), HTTPStatus.BAD_REQUEST

    return app


def run_app():
    """
    Method that is called from "flask run" (using .flaskenv).
    """

    logging.getLogger("tray_runner").setLevel(logging.DEBUG)
    config = Config.load_from_file(DEFAULT_CONFIG_FILE)
    dummy_app = DummyApp(config=config)
    execution_manager = ExecutionManager(dummy_app)
    return create_app(dummy_app, execution_manager, disable_flask_logs=False, auto_login_random=True)
