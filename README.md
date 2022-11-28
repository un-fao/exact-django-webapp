# EX-ACT 

### Prerequisites

- Python 3.8.0
- Pip
- Virtualenv (`pip install virtualenv`)
- Everything added to PATH (if on Windows)

### Installation Guide

1. Clone repository
2. Type `cd <path\to\repository>` in preferred terminal
3. Double-check requirements.txt for correct Python version
4. Install correct Python version on your machine if you don't have it
5. Conditional:
   1. If you have multiple Python versions installed, Run command `virtualenv env --python <path\to\correct\python\version>`
   2. If you only have Python 3.8.0 installed, simply run `virtual env`
6. Run command `source env\Scripts\activate`
7. Check if the virtual environment is active: do you see (env) in your terminal?
8. Run command `pip install -r requirements.txt`
10. Run command `python -m django manage.py migrate`
11. Run command `django manage.py runserver`
12. Enjoy

### How to dump IPCC Data in your local Database
1. Make sure you have installed 'django_extensions' with pip
2. Run `python manage.py runscript ipcc_dump`
3. Wait for termination