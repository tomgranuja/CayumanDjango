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
