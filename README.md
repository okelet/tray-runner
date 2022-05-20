# Tray Runner

Tray Runner is a simple application that runs in the system tray and executes periodically the commands configured. This is util when you want to run command line scripts without having a terminal open ow worry to remember to execute them.

The application has been tested on Linux (Ubuntu) and Windows 10, but should run on any modern operating system, as the UI relies on QT.

![Main configuration window](https://github.com/okelet/tray-runner/raw/main/docs/config_commands.png)

![Command configuration](https://github.com/okelet/tray-runner/raw/main/docs/command_general.png)

Check [more screenshots here](#more-screenshots).

## Installation

**Python 3.10 or greater is required**.

It is recommended to use [`pipx`](https://github.com/pypa/pipx) so you can install Tray Runner and its dependencies without affecting other applications installed with `pip`:

```bash
pipx install tray-runner
```

Check and upgrade with:

```bash
pipx upgrade tray-runner
```

In a near future, single file binaries will be provided.

Once installed, you can run the application running the command:

```bash
tray-runner-gui
```

Check the options running `tray-runner-gui --help`. The first time the program is executed, a shortcut in the applications menu and in the auto start directory will be created. Also, you will be asked to configure the application:

![First run](https://github.com/okelet/tray-runner/raw/main/docs/first_run.png)

### Fedora/RHEL based

```bash
sudo dnf install -y gnome-shell-extension-appindicator
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

Note: the indicator icon will be shown, but the notifications will remain in the notifications list.

## Running

From the CLI:

```bash
tray-runner-cli --help
```

From the GUI:

```bash
tray-runner-gui --help
```

## TODO

* Translations (raw Python and QT)
* One-file executables (and portables) for Linux and Windows
* Log viewer

## Development

### Translations

Update the template:

```bash
poetry run pybabel extract -o tray_runner/locale/messages.pot
```

Generate a new language:

```bash
poetry run pybabel init -l de_DE -i tray_runner/locale/messages.pot -d tray_runner/locale
```

Update the languages with the new translations found:

```bash
poetry run pybabel update -i tray_runner/locale/messages.pot -d tray_runner/locale
```

Compile the translations:

```bash
poetry run pybabel compile -d tray_runner/locale
```

### Code quality

Running directly the commands:

```bash
poetry run pylint tray_runner
poetry run black tray_runner
poetry run mypy tray_runner
poetry run isort tray_runner
```

Using `pre-commit`:

```bash
git add --intent-to-add .
poetry run pre-commit run --all-files
```

### Credits

* Icons:
  * [Fugue Icons](https://p.yusukekamiyamane.com/)
  * [Font Awesome](https://fontawesome.com/)
  * [Ikonate](https://ikonate.com/)

## More screenshots

List of commands:

![List of commands](https://github.com/okelet/tray-runner/raw/main/docs/config_commands.png)

General configuration:

![General configuration](https://github.com/okelet/tray-runner/raw/main/docs/config_general.png)

Commands common configuration:

![Commands common configuration](https://github.com/okelet/tray-runner/raw/main/docs/config_common.png)

Command configuration:

![Command configuration](https://github.com/okelet/tray-runner/raw/main/docs/command_general.png)

Command overrides:

![Command overrides](https://github.com/okelet/tray-runner/raw/main/docs/command_options.png)

Command environment variables:

![Command environment variables](https://github.com/okelet/tray-runner/raw/main/docs/command_environment.png)

Command statistics:

![Command statistics](https://github.com/okelet/tray-runner/raw/main/docs/command_statistics.png)
