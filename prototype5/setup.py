from setuptools import setup, find_packages # pragma: no cover

setup( # pragma: no cover
    name='syft',
    version='0.1.0',
    description='A plugin-based system for SyftBox',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/syft',
    packages=find_packages(exclude=['tests*']),
    install_requires=[
        'watchdog',
        'pytest',
        'pytest-cov',
    ],
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)