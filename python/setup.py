from setuptools import setup

description = "Please visit https://github.com/ResilienceTesting/gremlinsdk-python for more details about the usage and examples."

setup(
    name = 'pygremlin',
    version = '0.1.1',
    description = 'Python SDK for Gremlin framework',
    long_description=description,
    url='https://github.com/ResilienceTesting/gremlinsdk-python',
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
