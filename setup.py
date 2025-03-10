#!/usr/bin/env python3

"""
Setup script for the Protocol Agnostic Proxy Server.
"""

from setuptools import setup, find_packages

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='protocol-agnostic-proxy',
    version='0.1.0',
    description='A flexible, extensible proxy server for multiple protocols',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/protocol-agnostic-proxy',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'elasticsearch>=8.0.0',
        'elasticsearch-dsl>=8.0.0',
        'pyyaml>=6.0',
        'dpkt>=1.9.8',
        'scapy>=2.4.5',
        'python-dotenv>=0.19.0',
        'structlog>=22.1.0',
        'requests>=2.28.0',
        'python-dateutil>=2.8.2',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'black>=22.3.0',
            'pylint>=2.13.0',
            'mypy>=0.942',
        ],
    },
    entry_points={
        'console_scripts': [
            'proxy-server=src.main:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: System :: Networking :: Monitoring',
    ],
    python_requires='>=3.8',
)
