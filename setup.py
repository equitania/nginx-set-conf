# setup.py
from setuptools import setup, find_packages
from nginx_set_conf import __version__

setup(
    name='nginx_set_conf',
    version=__version__,
    description='Python library for generating nginx reverse proxy configurations for Docker applications.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Equitania Software GmbH',
    author_email='info@equitania.de',
    url='https://github.com/equitania/nginx-set-conf',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.2.1',
        'PyYAML>=6.0.2',
    ],
    entry_points={
        'console_scripts': [
            'nginx-set-conf = nginx_set_conf.nginx_set_conf:start_nginx_set_conf',
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Systems Administration",
    ],
    python_requires='>=3.10',
    keywords='nginx, configuration, docker, reverse-proxy',
)