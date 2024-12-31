"""Actions the project can perform."""

import os
import shutil


def build():
    """Build the project."""
    # Remove old build directory
    if os.path.exists("build"):
        shutil.rmtree("build")

    # Create new build directory
    os.makedirs("build")

    # Print success message
    print("Project built successfully!")
