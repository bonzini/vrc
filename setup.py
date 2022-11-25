from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='vrc',
    version='1.0.99',
    description='Call graph explorer tool',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Paolo Bonzini',
    author_email='bonzini@gnu.org',
    packages=['vrc', 'vrc.automata', 'vrc.cli', 'vrc.loaders'],
    install_requires=[
        'compynator'
    ],
    entry_points={
        'console_scripts': [
            'vrc = vrc.cli.main:main',
        ]
    }
)
