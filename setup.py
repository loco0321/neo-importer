from setuptools import setup
setup(
    name="neo-importer",
    version='0.2.16',
    author="Zina Team",
    author_email="support.zina@nokia.com",
    description="Provide utils for importer",
    long_description=open("README.md").read(),
    packages=[
        "neo_importer"
    ],
    include_package_data=True,
    #package_dir={'': '.'},
    install_requires=[
        'six==1.10.0',
        'xlwt==1.3.0',
        'xlrd==1.1.0',
        'xlutils==2.0.0',
        # 'python-ldap==2.4.22',
        # 'django-auth-ldap==1.2.7',
        # 'django-compressor==1.6',
        # 'djangorestframework==3.3.3',
        # 'markdown==2.6.5',
        # 'django-filter==0.13.0',
    ],
    classifiers=[
        "Development Status :: 3 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Framework :: Django",
    ],
    zip_safe=False
)

