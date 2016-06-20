"""
bikeseoul
=========

서울자전거 따릉이 연계 서비스.

"""
from setuptools import setup

setup(
    name='bikeseoul',
    url='https://github.com/bikeseoul/bikeseoul',
    zip_safe=False,
    packages=['bikeseoul', 'bikeseoul.web'],
    package_data={
        'bikeseoul.web': ['templates/*.*', 'templates/*/*.*',
                          'static/*.*', 'static/*/*.*'],
    },
    install_requires=[
        'Flask == 0.11',
        'SQLAlchemy == 1.0.13',
        'click == 6.6',
    ],
    entry_points={
        'console_scripts': ['bikeseoul = bikeseoul.cli:cli'],
    },
)
