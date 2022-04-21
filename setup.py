from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='vrc',
    version='1.0',
    description='Call graph explorer tool',
    author='Paolo Bonzini',
    author_email='bonzini@gnu.org',
    packages=['vrc'],
    entry_points={
        'console_scripts': [
            'vrc = vrc:main',
        ]
    }
)
