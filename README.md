# EX-ACT 

## Prerequisites

- Python 3.11.0
- Pip
- Virtualenv (`pip install virtualenv`)
- Everything added to PATH (if on Windows)

<br>

### [Click here to see the Django API Docs](http://localhost:8000/api/docs/) (make sure your local Django app is running)
### [Click here to see the Swagger API Docs](http://localhost:8000/api/swagger/) (make sure your local Django app is running)
### [Click here to see the Redoc API Docs](http://localhost:8000/api/redoc/) (make sure your local Django app is running)

<br>

### [Click here to download the Swagger .yaml](http://localhost:8000/api/swagger.yaml) (make sure your local Django app is running)
### [Click here to download the Swagger .json](http://localhost:8000/api/swagger.json) (make sure your local Django app is running)

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

    Alternatively,

    [![Run in Postman](https://run.pstmn.io/button.svg)](https://app.getpostman.com/run-collection/7002893-9d88940d-a037-477a-b287-d42e01c25749?action=collection%2Ffork&collection-url=entityId%3D7002893-9d88940d-a037-477a-b287-d42e01c25749%26entityType%3Dcollection%26workspaceId%3D7e75d44c-4b11-4375-afea-b500866e6198)