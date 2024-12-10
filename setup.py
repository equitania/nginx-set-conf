# setup.py
from setuptools import setup, find_packages

setup(
    name='nginx_set_conf',
    version='1.0.9',
    description='Ein Werkzeug zur Verwaltung von Nginx-Konfigurationen',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Equitania Software GmbH',
    author_email='info@equitania.de',
    url='https://github.com/equitania/nginx-set-conf',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.1.3',
        'PyYAML>=5.4.1',
    ],
    entry_points={
        'console_scripts': [
            'nginx-set-conf = nginx_set_conf.nginx_set_conf:start_nginx_set_conf',
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: System :: Systems Administration",
    ],
    python_requires='>=3.8',
    keywords='nginx, configuration, docker, reverse-proxy',
)