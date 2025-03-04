from setuptools import setup, find_packages

setup(
    name='certbot-dns-tencentcloud',
    version='3.0.0',
    author='KCN',
    author_email='realkcn@gmail.com',
    description='Tencent Cloud DNS Authenticator plugin for Certbot',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/realkcn/certbot-dns-tencentcloud",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'certbot>=1.18.0',
        'tencentcloud-sdk-python>=3.0.0',
    ],
    classifiers=[
        'Environment :: Plugins',
        'Intended Audience :: System Administrators',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Security',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Networking',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
    entry_points={
        'certbot.plugins': [
            'dns-tencentcloud = certbot_dns_tencentcloud.certbot_tencentcloud_plugins:Authenticator',
        ],
    },
)
