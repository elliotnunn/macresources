from setuptools import setup

setup(
    name='macresources',
    version='1.2',
    author='Elliot Nunn',
    author_email='elliotnunn@me.com',
    description='Library for working with legacy Macintosh resource forks',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    license='MIT',
    url='https://github.com/elliotnunn/macresources',
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Topic :: System :: Filesystems',
        'Development Status :: 3 - Alpha',
    ],
    packages=['macresources'],
    scripts=['bin/SimpleRez', 'bin/SimpleDeRez', 'bin/hexrez', 'bin/rezhex', 'bin/sortrez', 'bin/rfx', 'bin/greggybits', 'bin/instacomp'],
)
