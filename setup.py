from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="mini-devops-platform",
    version="1.0.0",
    author="Your Name",
    author_email="your@email.com",
    description="Automated Infrastructure Deployment CLI Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourname/mini-devops-platform",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "": ["templates/**/*", "config/**/*"],
    },
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "deploy_server=cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="devops automation infrastructure deployment ssh ansible",
)
