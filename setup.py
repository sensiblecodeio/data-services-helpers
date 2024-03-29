from distutils.core import setup

setup(
    name="dshelpers",
    version="2.0.0",
    description=(
        "Provides some helper functions used by The Sensible Code Company's Data"
        " Services team."
    ),
    long_description=(
        "Provides some helper functions used by the The Sensible Code Company's Data"
        " Services team."
    ),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    author="The Sensible Code Company Limited",
    author_email="dataservices@sensiblecode.io",
    url="https://github.com/sensiblecodeio/data-services-helpers",
    license="BSD",
    py_modules=["dshelpers"],
    install_requires=["requests", "requests_cache", "pytest", "scraperwiki"],
    extras_require={"dev": ["black", "flake8", "isort"]},
)
