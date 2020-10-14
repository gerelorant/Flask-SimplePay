from setuptools import setup
from os import path


this_directory = path.abspath(path.dirname(__file__))

with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='Flask-SimplePay',
    version='0.7',
    packages=['flask_simplepay'],
    url='https://github.com/gerelorant/Flask-SimplePay',
    license='MIT',
    author='Gere Lóránt',
    author_email='gerelorant@gmail.com',
    description='OTP SimplePay payment extension for Flask',
    include_package_data=True,
    long_description=long_description,
    long_description_content_type='text/markdown'
)
