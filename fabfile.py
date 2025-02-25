import sys

import tomli
from fabric import task
from invoke.exceptions import UnexpectedExit


def get_version():
    """Read version from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        data = tomli.load(f)
    return data["tool"]["poetry"]["version"]


@task
def deploy(ctx):
    """
    Deploy the latest version of the application.
    Run with: poetry run fab deploy
    """
    print("Starting deployment process...")

    try:
        # Enable maintenance mode
        print("\n1. Enabling maintenance mode...")
        ctx.run("poetry run python manage.py maintenance_mode on")

        print("\n2. Pulling latest changes from git...")
        ctx.run("git pull")

        print("\n3. Installing/updating dependencies...")
        ctx.run("poetry install")

        print("\n4. Running database migrations...")
        ctx.run("poetry run python manage.py migrate")

        print("\n5. Compiling translation messages...")
        ctx.run("poetry run python manage.py compilemessages")

        # Disable maintenance mode
        print("\n6. Disabling maintenance mode...")
        ctx.run("poetry run python manage.py maintenance_mode off")

        print("\n✨ Deployment completed successfully!")
        print("Remember that the changes are not actual until the webapp is reloaded in PythonAnywhere")

    except UnexpectedExit as e:
        print(f"\n❌ Deployment failed during step: {e.result.command}", file=sys.stderr)
        print(f"\nError output:\n{e.result.stderr or e.result.stdout}", file=sys.stderr)
        print("\n⚠️  Important notes:", file=sys.stderr)
        print("- Remember that the changes are not actual until the webapp is reloaded in PythonAnywhere", file=sys.stderr)
        print("- To avoid confusions with eventual visitors, it's recommended to activate maintenance mode with:", file=sys.stderr)
        print("  poetry run python manage.py maintenance_mode on", file=sys.stderr)
        print("  This way it will be possible to debug the site while avoiding confusions with the users", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during deployment: {str(e)}", file=sys.stderr)
        print("\n⚠️  Important notes:", file=sys.stderr)
        print("- Remember that the changes are not actual until the webapp is reloaded in PythonAnywhere", file=sys.stderr)
        print("- To avoid confusions with eventual visitors, it's recommended to activate maintenance mode with:", file=sys.stderr)
        print("  poetry run python manage.py maintenance_mode on", file=sys.stderr)
        print("  This way it will be possible to debug the site while avoiding confusions with the users", file=sys.stderr)
        sys.exit(1)


@task
def publish(ctx):
    """
    Create a version tag based on pyproject.toml version.
    Run with: poetry run fab publish
    """
    print("Starting publish process...")

    version = get_version()
    tag = f"v{version}"
    print(f"\nProject version from pyproject.toml: {version}")

    print(f"\n1. Checking if tag {tag} exists...")
    result = ctx.run(f"git tag -l {tag}", hide=True)
    if tag in result.stdout:
        print(f"⚠️  Tag {tag} already exists")
        return

    print(f"\n2. Creating new tag {tag}...")
    ctx.run(f"git tag {tag}")
    print(f"✓ Created tag {tag}")

    print("\n3. Pushing tag to remote repository...")
    ctx.run(f"git push origin {tag}")
    print(f"✨ Successfully pushed tag {tag} to origin")
