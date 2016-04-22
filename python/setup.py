from setuptools import setup

setup(
    name = 'pygremlin',
    version = '0.1',
    description = 'Python SDK for Gremlin framework',
    author = 'Shriram Rajagopalan',
    author_email = 'shriram@us.ibm.com',
    license = 'Apache 2.0',
    packages = ['pygremlin'],
    install_requires=[
        'requests',
        'networkx',
        'elasticsearch',
        'isodate'
      ],
    zip_safe = False
)
