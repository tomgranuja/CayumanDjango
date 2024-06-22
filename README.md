# Cayuman - School workshops inscription web form for students enrollment

## Install

Cayuman makes use of poetry and python3.10 or superior. Let's go step by step

## Installing python3.10

If you don't have the required python version installed then you can do so by following these instructions. Otherwise You can skip this section.

Start by installing `pyenv`, a python module that makes it easy to manage several different python versions.

```console
$ curl https://pyenv.run | bash
```

Then add `pyenv` to `.bash_profile` or your shell's profile file

```console
# pyenv
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

> Remember to run `source ~/.bash_profile` (or whatever's the name of your shell profile file) after adding the lines above.

Now install python3.10 by doing

```console
$ pyenv install 3.8
```

## Instaling poetry and getting your dev instance ready

Now it's time to install poetry

```console
$ pip install poetry
```

Then clone the repo

```console
$ git clone git@github.com:tomgranuja/CayumanDjango.git
```

and install the dev environment

```console
$ cd CayumanDjango
$ poetry install --with test
```

Install pre-commit hooks (to enforce coding standards)

```console
$ poetry run pre-commit install
```

## Running Tests

In order to run our tests you just have to do

```console
$ poetry run pytest
```

## Applying migrations

```console
$ poetry run python manage.py migrate
```

## Creating First Super User

```console
$ poetry run python manage.py createsuperuser
```

## Running dev server

```console
$ poetry run python manage.py runserver
```

## Generating new migrations

```console
$ poetry run python manage.py makemigrations
```

## Manage translation

```console
# Update translation file
$ poetry run python manage.py makemessages -l es

# Compile translation file
$ poetry run python manage.py compilemessages

# restart django server or webserver for changes to take effect
```

## Maintenance mode

If there's a need to set cayuman as maintenance mode, you must run this command

```console
$ python manage.py maintenance_mode <on|off>
```

# Conventions

These are some conventions or design decisions made by this project, which are not currently enforced by code or may not be so clear just from using it:

* A new entry on `StudentCycle`, meaning a relationship between a student and a cycle, is only added when the student is assigned to a different cycle. There's no need to create new `StudentCycle` entries for each student when periods change.
* `Period` entries are supposed to not collide in terms of `date_start` and `date_end` dates. Code force them not to. Collisions by `preview_date` or `enrollment_start` with another period's `date_end` are not prevented by code.
* There exists the method `PeriodManager.current` which returns the `Period` entry corresponding to the current date according to logic mainly based on `date_start` and `date_end`. If no period follows this then the method returns None.
* `StudentCycle` entries are considered to be "fully scheduled" during a period (`StudentCycle.is_schedule_full == True`) depending if a student cycle entries is associated with a `WorkshopPeriod` entry for each of the existing class blocks, and those `WorkshopPeriods` are associated with the given period.
