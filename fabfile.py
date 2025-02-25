import os
import sys

import tomli
from fabric import task
from invoke.exceptions import UnexpectedExit


def get_version():
    """Read version from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        data = tomli.load(f)
    return data["tool"]["poetry"]["version"]


def set_version(version):
    """Update version in pyproject.toml."""
    # Read the file content
    with open("pyproject.toml", "r") as f:
        content = f.read()

    # Replace the version line
    import re

    new_content = re.sub(r'version = "[^"]+"', f'version = "{version}"', content)

    # Write back
    with open("pyproject.toml", "w") as f:
        f.write(new_content)


def bump_patch_version(version):
    """Bump the patch version (z) in x.y.z."""
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def has_uncommitted_changes(ctx):
    """Check if there are uncommitted changes."""
    result = ctx.run("git status --porcelain", hide=True)
    return bool(result.stdout.strip())


def get_commit_for_tag(ctx, tag):
    """Get the commit hash for a tag, or None if tag doesn't exist."""
    try:
        result = ctx.run(f"git rev-parse {tag}", hide=True)
        return result.stdout.strip()
    except UnexpectedExit:
        return None


def get_current_commit(ctx):
    """Get the current HEAD commit hash."""
    result = ctx.run("git rev-parse HEAD", hide=True)
    return result.stdout.strip()


def get_current_branch(ctx):
    """Get the name of the current git branch."""
    result = ctx.run("git rev-parse --abbrev-ref HEAD", hide=True)
    return result.stdout.strip()


def ensure_main_branch(ctx):
    """Ensure we're on the main branch, exit if not."""
    branch = get_current_branch(ctx)
    if branch != "main":
        print(f"❌ Error: Must be on 'main' branch, but current branch is '{branch}'", file=sys.stderr)
        print("Please switch to main branch and try again", file=sys.stderr)
        sys.exit(1)


@task
def deploy(ctx):
    """
    Deploy the latest version of the application.
    Run with: poetry run fab deploy
    """
    # Check if we're in PythonAnywhere environment
    if not os.getenv("PYTHONANYWHERE_DOMAIN") or not os.getenv("PYTHONANYWHERE_SITE"):
        print("❌ Error: This command can only be run in PythonAnywhere environment", file=sys.stderr)
        sys.exit(1)

    print("Starting deployment process...")

    # Ensure we're on main branch
    ensure_main_branch(ctx)

    try:
        print("\n1. Pulling latest changes from git...")
        ctx.run("git pull")

        print("\n2. Installing/updating dependencies...")
        ctx.run("poetry install")

        print("\n3. Running database migrations...")
        ctx.run("poetry run python manage.py migrate")

        print("\n4. Compiling translation messages...")
        ctx.run("poetry run python manage.py compilemessages")

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

    # Ensure we're on main branch
    ensure_main_branch(ctx)

    # Check for uncommitted changes
    if has_uncommitted_changes(ctx):
        print("❌ Error: You have uncommitted changes.", file=sys.stderr)
        print("Please commit or stash your changes before publishing.", file=sys.stderr)
        sys.exit(1)

    # Get current version and tag
    version = get_version()
    tag = f"v{version}"
    print(f"\nProject version from pyproject.toml: {version}")

    # Get commit hashes
    current_commit = get_current_commit(ctx)
    tag_commit = get_commit_for_tag(ctx, tag)

    # If tag exists, check if we need to bump version
    if tag_commit:
        if tag_commit != current_commit:
            print(f"\n🔄 Current HEAD differs from {tag}, bumping version...")
            new_version = bump_patch_version(version)
            new_tag = f"v{new_version}"

            # Check if the new version tag already exists
            if get_commit_for_tag(ctx, new_tag):
                print(f"\n❌ Error: After bumping version, tag {new_tag} already exists!", file=sys.stderr)
                print("This might indicate version conflicts or an inconsistent state.", file=sys.stderr)
                print("Please check the project's version history and set the version manually in pyproject.toml", file=sys.stderr)
                sys.exit(1)

            set_version(new_version)
            print(f"Version bumped to {new_version}")

            # Commit the version change
            ctx.run("git add pyproject.toml")
            ctx.run(f'git commit -m "chore: bump version to {new_version}"')
            print("✓ Committed version change")

            # Push the commit
            print("\n1. Pushing version bump to remote...")
            ctx.run("git push origin main")
            print("✓ Pushed version bump")

            # Create and push the tag
            print(f"\n2. Creating tag {new_tag}...")
            ctx.run(f"git tag {new_tag}")
            print(f"✓ Created tag {new_tag}")

            print("\n3. Pushing tag to remote repository...")
            ctx.run(f"git push origin {new_tag}")
            print(f"✨ Successfully pushed tag {new_tag} to origin")
            sys.exit(0)
        else:
            print(f"\n⚠️  Tag {tag} already exists and points to current commit")
            print("No action needed")
            sys.exit(0)

    # Create and push the tag for existing version
    print(f"\n1. Creating tag {tag}...")
    ctx.run(f"git tag {tag}")
    print(f"✓ Created tag {tag}")

    print("\n2. Pushing tag to remote repository...")
    ctx.run(f"git push origin {tag}")
    print(f"✨ Successfully pushed tag {tag} to origin")
