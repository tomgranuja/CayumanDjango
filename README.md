# Cayuman - School workshops inscription web form for students enrollment

## Install

Cayuman makes use of poetry and python3.10 or superior. Let's go step by step

## Installing python3.10

If you don't have the required python version installed then you can do so by following these instructions. Otherwise You can skip this section.

Start by installing `pyenv`, a python module that makes it easy to manage several different python versions.

```bash
curl https://pyenv.run | bash
```

Then add `pyenv` to `.bash_profile` or your shell's profile file

```bash
# pyenv
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

> Remember to run `source ~/.bash_profile` (or whatever's the name of your shell profile file) after adding the lines above.

Now install python3.10 by doing

```bash
pyenv install 3.8
```

## Instaling poetry and getting your dev instance ready

Now it's time to install poetry

```bash
pip install poetry
```

Then clone the repo

```bash
git clone git@github.com:tomgranuja/CayumanDjango.git
```

and install the dev environment

```bash
cd CayumanDjango
poetry install --with test
```

Install pre-commit hooks (to enforce coding standards)

```bash
poetry run pre-commit install
```

## Running Tests

In order to run our tests you just have to do

```bash
poetry run pytest
```

## Applying migrations

```bash
poetry run python manage.py migrate
```

## Creating First Super User

```bash
poetry run python manage.py createsuperuser
```

## Running dev server

```bash
poetry run python manage.py runserver
```

## Generating new migrations

```bash
poetry run python manage.py makemigrations
```

## Manage translation

```bash
# Update translation file
poetry run python manage.py makemessages -l es

# Compile translation file
poetry run python manage.py compilemessages

# restart django server or webserver for changes to take effect
```

## Deployment

When deploying cayuman, you must run the following commands:

```bash
git pull
poetry install
poetry run python manage.py migrate
poetry run python manage.py compilemessages
```

## Maintenance mode

If there's a need to set cayuman as maintenance mode, you must run this command

```bash
python manage.py maintenance_mode <on|off>
```

## Custom Permissions

Cayuman implements a custom permission system that extends Django's default permission system. This is done through:

1. A custom permission backend (`CayumanPermissionBackend`) that checks permissions before falling back to Django's default behavior
2. A permission registry system that allows registering custom permission checks using decorators

### How it works

1. Custom permissions are registered using the `@register_permission` decorator in `permissions.py`
2. Each permission is a function that takes a user and optional object parameter
3. The custom backend checks these permissions before falling back to Django's default system

### Example

```python
@register_permission("cayuman.can_enroll")
def can_enroll(user: Member, obj: Period = None):
    # Check if the user is a student, the period is current, and enrollment is enabled
    if obj is None:
        return False
    return obj.is_current() and user.is_student and user.is_enabled_to_enroll(obj)
```

### Configuration

The custom permission backend is enabled in settings.py:

```python
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # default Django auth backend
    'cayuman.backends.CayumanPermissionBackend',  # custom permission backend
]
```

### Existing Custom Permissions

Currently, the system has the following custom permissions:

#### `cayuman.can_enroll`

This permission controls whether a user can enroll in workshops for a given period. The permission check:

1. Requires the user to be a student
2. Requires the period to be current
3. Checks if enrollment is enabled for the user in that period through `user.is_enabled_to_enroll(period)`

This permission is used in:

- Enrollment views to control access to workshop registration
- View decorators like `@enrollment_access_required`
- Template conditions to show/hide enrollment-related UI elements

The permission is particularly important because it handles various enrollment scenarios:

- Regular student enrollment during the enrollment period
- Late enrollment for students without a full schedule
- Administrative enrollment by superusers
- Preventing enrollment in past or future periods

## Conventions

These are some conventions or design decisions made by this project, which are not currently enforced by code or may not be so clear just from using it:

* A new entry on `StudentCycle`, meaning a relationship between a student and a cycle, is only added when the student is assigned to a different cycle. There's no need to create new `StudentCycle` entries for each student when periods change.
* `Period` entries are supposed to not collide in terms of `date_start` and `date_end` dates. Code force them not to. Collisions by `preview_date` or `enrollment_start` with another period's `date_end` are not prevented by code.
* There exists the method `PeriodManager.current` which returns the `Period` entry corresponding to the current date according to logic mainly based on `date_start` and `date_end`. If no period follows this then the method returns None.
* `StudentCycle` entries are considered to be "fully scheduled" during a period (`StudentCycle.is_schedule_full == True`) depending if a student cycle entries is associated with a `WorkshopPeriod` entry for each of the existing class blocks, and those `WorkshopPeriods` are associated with the given period.
