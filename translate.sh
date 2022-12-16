#!/bin/bash

poetry run pybabel extract -F babel.cfg -k lazy_gettext -o tray_runner/translations/messages.pot .
poetry run pybabel update -i tray_runner/translations/messages.pot -d tray_runner/translations
poetry run pybabel compile -d tray_runner/translations
