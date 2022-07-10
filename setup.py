import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="nginx-set-conf-equitania",
    version="0.7.6",
    author="Equitania Software GmbH",
    author_email="info@equitania.de",
    description="A package to create configurations for nginx with/without pagespeed for different web applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=['nginx_set_conf'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points='''
    [console_scripts]
    nginx-set-conf=nginx_set_conf.nginx_set_conf:start_nginx_set_conf
    ''',
    install_requires=[
        'click>=8.1.3',
        'PyYaml>=6.0'
    ]
)