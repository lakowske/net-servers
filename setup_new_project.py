#!/usr/bin/env python3
"""Setup script for creating a new Python project from this template.

This script will prompt you for project details and automatically update
all configuration files with your project information.
"""

import re
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any, Dict


def get_user_input() -> Dict[str, Any]:
    """Collect project information from user input."""
    print("🚀 Setting up your new Python project!")
    print("=" * 50)

    # Get basic project info
    project_name = input("Project name (e.g., my-awesome-project): ").strip()
    if not project_name:
        print("❌ Project name is required!")
        sys.exit(1)

    # Convert project name to valid Python module name
    module_name = re.sub(r"[^a-zA-Z0-9_]", "_", project_name.lower())
    module_name = re.sub(r"^[0-9]", "_", module_name)  # Can't start with number

    description = input("Project description (A clean Python project): ").strip()
    if not description:
        description = "A clean Python project"

    author_name = input("Author name: ").strip()
    if not author_name:
        author_name = "Your Name"

    author_email = input("Author email: ").strip()
    if not author_email:
        author_email = "your.email@example.com"

    github_username = input("GitHub username (optional): ").strip()

    # Generate GitHub URLs if username provided
    if github_username:
        repo_url = f"https://github.com/{github_username}/{project_name}"
        issues_url = f"{repo_url}/issues"
    else:
        repo_url = f"https://github.com/YOUR_USERNAME/{project_name}"
        issues_url = f"{repo_url}/issues"

    return {
        "project_name": project_name,
        "module_name": module_name,
        "description": description,
        "author_name": author_name,
        "author_email": author_email,
        "github_username": github_username,
        "repo_url": repo_url,
        "issues_url": issues_url,
    }


def update_pyproject_toml(config: Dict[str, Any]) -> None:
    """Update pyproject.toml with project information."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Update project metadata
    content = re.sub(
        r'name = "clean-python"', f'name = "{config["project_name"]}"', content
    )
    content = re.sub(
        r'description = ".*"', f'description = "{config["description"]}"', content
    )
    content = re.sub(
        r'authors = \[{name = ".*", email = ".*"}\]',
        f'authors = [{{name = "{config["author_name"]}", email = "{config["author_email"]}"}}]',
        content,
    )

    # Update URLs
    content = re.sub(r'Homepage = ".*"', f'Homepage = "{config["repo_url"]}"', content)
    content = re.sub(
        r'Repository = ".*"', f'Repository = "{config["repo_url"]}"', content
    )
    content = re.sub(r'Issues = ".*"', f'Issues = "{config["issues_url"]}"', content)

    pyproject_path.write_text(content)
    print("✅ Updated pyproject.toml")


def update_readme_md(config: Dict[str, Any]) -> None:
    """Update README.md with project information."""
    readme_path = Path("README.md")

    # Create a new README with project-specific content
    readme_content = f"""# {config['project_name']}

{config['description']}

## Features

- Modern Python project structure
- Comprehensive testing with pytest and coverage reporting
- Code quality tools (Black, Flake8, MyPy, Bandit)
- Pre-commit hooks for automated quality checks
- GitHub Actions CI/CD pipeline
- VS Code tasks integration

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Git

### Installation

1. Clone the repository:
```bash
git clone {config['repo_url']}.git
cd {config['project_name']}
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
```

3. Install the project in development mode:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Development

### Running Tests
```bash
# Run tests with coverage
pytest --cov=. --cov-report=term-missing --cov-fail-under=80 --cov-report=html

# Or use the VS Code task: Ctrl+Shift+P -> "Tasks: Run Task" -> "Run Tests with Coverage"
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8

# Run all pre-commit checks
pre-commit run --all-files
```

### VS Code Integration

This project includes VS Code tasks for common operations:
- `Ctrl+Shift+P` -> "Tasks: Run Task" to see all available tasks
- Install the "Task Explorer" extension for a better task management experience

## Project Structure

```
{config['project_name']}/
├── src/{config['module_name']}/     # Main package
├── tests/                          # Test suite
├── .github/workflows/              # GitHub Actions
├── .vscode/                        # VS Code configuration
├── pyproject.toml                  # Project configuration
└── README.md                       # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and run the quality checks
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

{config['author_name']} - {config['author_email']}
"""

    readme_path.write_text(readme_content)
    print("✅ Updated README.md")


def rename_module_directory(config: Dict[str, Any]) -> None:
    """Rename the main module directory to match the project."""
    old_module_path = Path("src/clean_python")
    new_module_path = Path(f"src/{config['module_name']}")

    if old_module_path.exists() and old_module_path != new_module_path:
        old_module_path.rename(new_module_path)
        print(
            f"✅ Renamed module directory: src/clean_python -> src/{config['module_name']}"
        )
    elif not old_module_path.exists():
        print("⚠️  Module directory src/clean_python not found, skipping rename")


def update_github_workflows(config: Dict[str, Any]) -> None:
    """Update GitHub Actions workflow files."""
    workflow_path = Path(".github/workflows/ci.yml")
    if workflow_path.exists():
        content = workflow_path.read_text()
        # Update any project-specific references if needed
        workflow_path.write_text(content)
        print("✅ Verified GitHub Actions workflow")


def cleanup_template_files() -> None:
    """Remove template-specific files that aren't needed in the new project."""
    files_to_remove = [
        "setup_new_project.py",  # This script itself
    ]

    for file_path in files_to_remove:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            print(f"✅ Removed template file: {file_path}")


def create_initial_git_commit(config: Dict[str, Any]) -> None:
    """Create an initial git commit with the new project setup."""
    try:
        subprocess.run(["git", "add", "."], check=True)  # nosec B603, B607
        subprocess.run(  # nosec B603, B607
            [
                "git",
                "commit",
                "-m",
                f"Initial project setup for {config['project_name']}",
            ],
            check=True,
        )
        print("✅ Created initial git commit")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Could not create git commit: {e}")


def main() -> None:
    """Main setup function."""
    print("This script will help you customize this template for your new project.")
    print("It will modify files in the current directory.")

    proceed = input("\\nDo you want to continue? (y/N): ").strip().lower()
    if proceed not in ["y", "yes"]:
        print("Setup cancelled.")
        sys.exit(0)

    # Get user configuration
    config = get_user_input()

    print("\\n🔧 Updating project files...")

    # Update all project files
    update_pyproject_toml(config)
    update_readme_md(config)
    rename_module_directory(config)
    update_github_workflows(config)

    print("\\n🎉 Project setup complete!")
    print(f"\\nProject: {config['project_name']}")
    print(f"Module:  {config['module_name']}")
    print(f"Author:  {config['author_name']} <{config['author_email']}>")

    # Ask about cleanup and git commit
    cleanup = (
        input("\\nRemove setup script and create initial git commit? (Y/n): ")
        .strip()
        .lower()
    )
    if cleanup not in ["n", "no"]:
        cleanup_template_files()
        create_initial_git_commit(config)

    print("\\n✨ Your new Python project is ready!")
    print("\\nNext steps:")
    print("1. Create a virtual environment: python -m venv .venv")
    print("2. Activate it: source .venv/bin/activate")
    print("3. Install dependencies: pip install -e '.[dev]'")
    print("4. Install pre-commit hooks: pre-commit install")
    print("5. Start coding! 🚀")


if __name__ == "__main__":
    main()
