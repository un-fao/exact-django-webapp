# EX-ACT 

## Prerequisites

- Python 3.11.0
- Pip
- Virtualenv (`pip install virtualenv`)
- Everything added to PATH (if on Windows)

<br>

### [Click here to see the API's Docs](http://localhost:8000/api/docs/) (make sure your local Django app is running)

<br>

## Installation Guide
1. Clone repository
2. Type `cd <path\to\repository>` in your preferred terminal
3. Double-check that you have the required Python version
4. Install the correct Python version on your machine if you don't have it
5. If you have multiple Python versions installed, Run command `virtualenv env --python <path\to\correct\python\version>`, otherwise just run `virtualenv env`
6. Run command `source env/Scripts/activate` (use forward or backslashes depending on your OS)
7. Check if the virtual environment is active: do you see (env) in your terminal?
8. Run command `pip install -r requirements.txt`
9. Run command `cd djangoexact`
10. Run command `python -m manage.py migrate`
11. Run command `python -m manage.py createsuperuser` and fill it with your preferred credentials (ex. usr:admin, pwd:admin)
12. Run command `django manage.py runserver`
13. Enjoy

<br>

## How to dump IPCC Data in your local Database

1. Make sure you have installed **django_extensions** with pip (check with command `pip list` while inside your virtual environment)
2. Run `python manage.py runscript ipcc_dump`
3. Wait for completion (it might take a while)

## How to use the Postman collection of currently-working requests

1. [Download Postman](https://www.postman.com/downloads/)
2. Import file `EX-ACT.postman_collection.json`