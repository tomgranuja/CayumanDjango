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

## Development

### Keeping dependencies up to date

After pulling latest changes from the repository, always run:

```bash
poetry install --with test
```

This ensures your development environment has all the required dependencies, including testing tools.

### Generating new migrations

```bash
poetry run python manage.py makemigrations
```

### Managing translations

```bash
# Update translation file
poetry run python manage.py makemessages -l es

# Compile translation file
poetry run python manage.py compilemessages

# restart django server or webserver for changes to take effect
```

### Publishing Changes

When you want to push changes to production:

1. Make sure your changes are committed and pushed to the main branch
2. Switch to main branch if you're not already on it
3. Update the version in pyproject.toml if needed
4. Run the publish command:

```bash
poetry run fab publish
```

To see all available commands:

```bash
poetry run fab --list
```

The publish command handles version management automatically:

- If you're not on the main branch, it will stop and ask you to switch to it
- If you have uncommitted changes, it will stop and ask you to commit or stash them
- If the current version tag already exists but points to a different commit:
  - It will automatically bump the patch version (z in x.y.z)
  - If the bumped version tag already exists, it will stop and ask for manual version setting
  - Otherwise, it will:
    1. Commit the version bump with message "chore: bump version to x.y.z"
    2. Push the commit to the remote main branch
    3. Create and push the new version tag
- If the current version tag exists and points to the current commit:
  - It will stop as no action is needed
- If the version tag doesn't exist:
  - It will create and push the tag to the remote repository

This ensures that each set of changes gets a unique version number and proper git tag.

## Deployment

The recommended way to deploy Cayuman is using the provided Fabric command:

```bash
poetry run fab deploy
```

This command will:

- Only work on the main branch
- Only run in PythonAnywhere environment (requires PYTHONANYWHERE_DOMAIN and PYTHONANYWHERE_SITE env vars)
- Automatically execute all deployment steps in the correct order:
  1. Pull latest changes from git
  2. Generate a fresh poetry.lock file to ensure up-to-date dependencies
  3. Run database migrations
  4. Compile translation messages

Note: The project intentionally does not track poetry.lock in git to ensure each deployment gets the latest compatible package versions. The lock file is generated fresh during deployment.

### Manual Deployment

If you need to run the deployment steps manually, execute these commands in order:

```bash
git pull
rm -f poetry.lock  # Remove existing lock file
poetry install     # Generate fresh lock file
poetry run python manage.py migrate
poetry run python manage.py compilemessages
```

## Maintenance mode

If there's a need to set cayuman as maintenance mode, you must run this command

```bash
poetry run python manage.py maintenance_mode <on|off>
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

- A new entry on `StudentCycle`, meaning a relationship between a student and a cycle, is only added when the student is assigned to a different cycle. There's no need to create new `StudentCycle` entries for each student when periods change.
- `Period` entries are supposed to not collide in terms of `date_start` and `date_end` dates. Code force them not to. Collisions by `preview_date` or `enrollment_start` with another period's `date_end` are not prevented by code.
- There exists the method `PeriodManager.current` which returns the `Period` entry corresponding to the current date according to logic mainly based on `date_start` and `date_end`. If no period follows this then the method returns None.
- `StudentCycle` entries are considered to be "fully scheduled" during a period (`StudentCycle.is_schedule_full == True`) depending if a student cycle entries is associated with a `WorkshopPeriod` entry for each of the existing class blocks, and those `WorkshopPeriods` are associated with the given period.
