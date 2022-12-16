"""
tray_runner.flask_forms module.
"""
import logging
from typing import List, Tuple

from croniter import croniter
from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import BooleanField, Field, IntegerField, SelectField, StringField, ValidationError
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Regexp
from wtforms.widgets import TextArea

from tray_runner.config import Config, ConfigCommand, ConfigCommandRunMode, ConfigCommandScheduleMode, LogLevelEnum, YesNoDefault

LOG = logging.getLogger(__name__)
COMMAND_ID_REGEX = "^(?![-_])[a-z0-9-_]+(?<![-_])$"
YES_NO_DEFAULT_CHOICES: List[Tuple[str, str]] = [(data.value, data.display_name()) for data in YesNoDefault]
RUN_MODE_CHOICES: List[Tuple[str, str]] = [(data.value, data.display_name()) for data in ConfigCommandRunMode]
SCHEDULE_MODE_CHOICES: List[Tuple[str, str]] = [(data.value, data.display_name()) for data in ConfigCommandScheduleMode]
LOG_LEVEL_CHOICES: List[Tuple[str, str]] = [(data.value, data.display_name()) for data in LogLevelEnum]


def str_to_log_level(log_level_str: str) -> LogLevelEnum:
    return LogLevelEnum[log_level_str]


def str_to_yes_no_default_enum(yes_no_default_str: str) -> YesNoDefault:
    return YesNoDefault[yes_no_default_str]


def str_to_run_mode(run_mode_str: str) -> ConfigCommandRunMode:
    return ConfigCommandRunMode[run_mode_str]


def str_to_schedule_mode(schedule_mode_str: str) -> ConfigCommandScheduleMode:
    return ConfigCommandScheduleMode[schedule_mode_str]


def command_id_validator(config: Config, command: ConfigCommand, _form: FlaskForm, field: Field):
    """
    Check that the ID in the form is not being used by another command.
    """
    LOG.debug("Checking command ID (ID to check: %s, command ID being edited: %s)...", field.data, command.id)
    for command_tmp in config.commands:
        if command_tmp != command:
            if command_tmp.id == field.data:
                raise ValidationError(lazy_gettext("ID already being used."))


class CommandEnvironmentVariableForm(FlaskForm):
    """
    Form class to display a command environment variable.
    """

    name = StringField()
    value = StringField()


class CommandForm(FlaskForm):
    """
    Form class for a command.
    """

    id = StringField(label=lazy_gettext("ID"), description=lazy_gettext("ID of the command; can only contain letters, numbers, dashes and underscores."), validators=[InputRequired(), DataRequired(), Length(min=4, max=32), Regexp(COMMAND_ID_REGEX)], render_kw={"data-section": "general"})
    name = StringField(label=lazy_gettext("Name"), description=lazy_gettext("Descriptive name of the command."), validators=[InputRequired(), DataRequired(), Length(min=4, max=128)], render_kw={"data-section": "general"})
    description = StringField(label=lazy_gettext("Description of the command."), widget=TextArea(), render_kw={"rows": "5", "data-section": "general"})
    disabled = BooleanField(label=lazy_gettext("Disabled"), description=lazy_gettext("Whether the command is disabled or enabled; if it is disabled, it won't run in an automated way (only when run manually)."), render_kw={"data-section": "general"})
    max_log_count = IntegerField(label=lazy_gettext("Maximum number of logs"), validators=[NumberRange(10, 999)], render_kw={"data-section": "general"})

    working_directory = StringField(label=lazy_gettext("Working directory"), validators=[InputRequired(), DataRequired()], render_kw={"data-section": "run"})
    run_mode = SelectField(label=lazy_gettext("Run mode"), choices=RUN_MODE_CHOICES, coerce=str_to_run_mode, render_kw={"data-section": "run"})
    command = StringField(label=lazy_gettext("Command"), description=lazy_gettext("Command to run."), render_kw={"data-section": "run"})
    script_interpreter = StringField(label=lazy_gettext("Script interpreter"), description=lazy_gettext("Script interpreter to use to run the script below; only valid for Windows."), render_kw={"data-section": "run"})
    script = StringField(label=lazy_gettext("Script"), widget=TextArea(), description=lazy_gettext("Script to run."), render_kw={"rows": "25", "data-section": "run"})

    schedule_mode = SelectField(label=lazy_gettext("Schedule mode"), choices=SCHEDULE_MODE_CHOICES, coerce=str_to_schedule_mode, render_kw={"data-section": "schedule"})
    run_at_startup = BooleanField(label=lazy_gettext("Run at startup"), render_kw={"data-section": "schedule"})
    run_at_startup_if_missing_previous_run = BooleanField(label=lazy_gettext("Run at startup if missing previous run"), render_kw={"data-section": "schedule"})
    period_seconds = IntegerField(render_kw={"data-section": "schedule"})
    cron_expr = StringField(label=lazy_gettext("Cron expression"), render_kw={"data-section": "schedule"})
    startup_delay_seconds = IntegerField(render_kw={"data-section": "schedule"})

    run_in_shell = SelectField(label=lazy_gettext("Run in shell"), validators=[InputRequired()], choices=YES_NO_DEFAULT_CHOICES, coerce=str_to_yes_no_default_enum, render_kw={"data-section": "options"})
    include_output_in_notifications = SelectField(label=lazy_gettext("Include output in notifications"), validators=[InputRequired()], choices=YES_NO_DEFAULT_CHOICES, coerce=str_to_yes_no_default_enum, render_kw={"data-section": "options"})
    show_complete_notifications = SelectField(label=lazy_gettext("Show notifications on complete"), validators=[InputRequired()], choices=YES_NO_DEFAULT_CHOICES, coerce=str_to_yes_no_default_enum, render_kw={"data-section": "options"})
    show_error_notifications = SelectField(label=lazy_gettext("Show notifications on error"), validators=[InputRequired()], choices=YES_NO_DEFAULT_CHOICES, coerce=str_to_yes_no_default_enum, render_kw={"data-section": "options"})

    # environment = FieldList(FormField(CommandEnvironmentVariableForm), label=lazy_gettext("Environment"))

    @staticmethod
    def validate_cron_expr(form: FlaskForm, field: Field):
        schedule_mode = ConfigCommandScheduleMode[form["schedule_mode"].data]
        if schedule_mode == ConfigCommandScheduleMode.CRON:
            cron_expr = field.data
            if not cron_expr:
                raise ValidationError(lazy_gettext("This field is mandatory when the schedule mode is set to Cron."))
            if not croniter.is_valid(cron_expr):
                raise ValidationError(lazy_gettext("The expression not valid."))

    @staticmethod
    def validate_command(form: FlaskForm, field: Field):
        run_mode = ConfigCommandRunMode[form["run_mode"].data]
        if run_mode == ConfigCommandRunMode.COMMAND:
            command = field.data
            if not command:
                raise ValidationError(lazy_gettext("This field is mandatory when the run mode is set to Command."))

    @staticmethod
    def validate_script(form: FlaskForm, field: Field):
        run_mode = ConfigCommandRunMode[form["run_mode"].data]
        if run_mode == ConfigCommandRunMode.SCRIPT:
            script = field.data
            if not script:
                raise ValidationError(lazy_gettext("This field is mandatory when the run mode is set to Script."))

    @staticmethod
    def validate_script_interpreter(form: FlaskForm, field: Field):
        run_mode = ConfigCommandRunMode[form["run_mode"].data]
        if run_mode == ConfigCommandRunMode.SCRIPT:
            script_interpreter = field.data
            if not script_interpreter:
                raise ValidationError(lazy_gettext("This field is mandatory when the run mode is set to Script."))


class SettingsForm(FlaskForm):
    """
    Form class for the settings.
    """

    language = SelectField(label=lazy_gettext("Language"), validators=[InputRequired(), DataRequired()], render_kw={"data-section": "general"})
    log_level = SelectField(label=lazy_gettext("Log level"), validators=[InputRequired(), DataRequired()], choices=LOG_LEVEL_CHOICES, coerce=str_to_log_level, render_kw={"data-section": "general"})
    create_app_menu_shortcut = BooleanField(label=lazy_gettext("Create shortcut in applications menu"), render_kw={"data-section": "general"})
    auto_start = BooleanField(label=lazy_gettext("Auto start on login"), render_kw={"data-section": "general"})

    run_in_shell = BooleanField(label=lazy_gettext("Run in shell"), render_kw={"data-section": "defaults"})
    include_output_in_notifications = BooleanField(label=lazy_gettext("Include output in notifications"), render_kw={"data-section": "defaults"})
    show_complete_notifications = BooleanField(label=lazy_gettext("Show notifications on complete"), render_kw={"data-section": "defaults"})
    show_error_notifications = BooleanField(label=lazy_gettext("Show notifications on error"), render_kw={"data-section": "defaults"})
