import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="nginx-set-conf-equitania",
    version="0.0.6",
    author="Lukas von Ehr - Equitania Software GmbH",
    author_email="l.von.ehr@equitania.de",
    description="A package to create configurations for docker based applications",
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
        'click>=7.1.2',
        'PyYaml>=3.12'
    ]
)