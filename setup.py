'''
Twitter Bot Giveaway python package configuration
Matt Auer <mattauer@umich.edu>
'''

from setuptools import setup

setup(
    name='twitter_bot',
    version='0.1.0',
    packages=['twitter_bot'],
    include_package_data=True,
    install_requires=[
        'Flask==1.1.2',
        'requests==2.25.1',
        'requests-oauthlib==1.3.0',
        'pycodestyle==2.6.0',
        'pydocstyle==5.1.1',
        'pylint==2.6.0',
        'bs4==0.0.1',
    ],
)