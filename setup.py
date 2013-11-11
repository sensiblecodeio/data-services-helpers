from setuptools import setup, find_packages

long_desc = """
Provides some helpers functions used by the ScraperWiki Data Services team.
"""
# See https://pypi.python.org/pypi?%3Aaction=list_classifiers for classifiers

setup(
    name='dshelpers',
    version='1.0.1',
    description="Extract fields from tabular data with complex expressions.",
    long_description=long_desc,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
    ],
    keywords='',
    author='ScraperWiki Limited',
    author_email='dataservices@scraperwiki.com',
    url='http://scraperwiki.com',
    license='BSD',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=[],
    include_package_data=False,
    zip_safe=False,
    install_requires=[
        'requests',
        'requests_cache',
        'mock',
    ],
    tests_require=[],
    entry_points=\
    """
    """,
)
