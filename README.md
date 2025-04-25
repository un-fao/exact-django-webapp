# EX-ACT API

EX-ACT (Ex-Ante Carbon Balance Tool) is a Django REST Framework-based API that provides a comprehensive system for carbon balance analysis and greenhouse gas emissions calculations. This tool is designed to help estimate the impact of agriculture, forestry, and other land use projects on carbon balance and greenhouse gas emissions. It is built for direct use of the [EX-ACT Web Tool](https://exact.apps.fao.org/), but its IPCC dataset is freely accessible upon request and grant of the proper permissions to the CSI team.

## 🌟 Features

- **Comprehensive API Documentation**: Available in multiple formats
  - Django API Docs (`/api/docs/`)
  - Swagger UI (`/api/swagger/`)
  - ReDoc (`/api/redoc/`)
  - OpenAPI Specifications (downloadable in JSON and YAML formats)

- **Advanced Calculation Modules**:
  - Carbon balance assessment
  - Greenhouse gas emissions calculations
  - IPCC data integration
  - Customizable parameters and coefficients

- **Security Features**:
  - Token-based authentication
  - Role-based access control
  - Secure API endpoints

- **Data Management**:
  - IPCC data integration
  - Project data storage and retrieval
  - Report generation capabilities

## 🔧 Prerequisites

- Python 3.11.0
- pip (Python package manager)
- virtualenv (`pip install virtualenv`)
- Node.js and npm (for frontend assets)

## 🚀 Quick Start

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. **Set Up Virtual Environment**
   ```bash
   # Create virtual environment
   virtualenv env --python=python3.11
   
   # Activate virtual environment
   # On Unix or MacOS:
   source env/bin/activate
   # On Windows:
   source env/Scripts/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database Setup**
   ```bash
   cd djangoexact
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

   The API will be available at `http://localhost:8000/api/`

## 📊 IPCC Data Integration

To populate your database with IPCC data:

1. Ensure `django_extensions` is installed (included in requirements.txt)
2. Run the data import script:
   ```bash
   python manage.py runscript ipcc_dump
   ```

## 🔍 API Testing

### Using Postman

1. Download [Postman](https://www.postman.com/downloads/)
2. Import the provided collection:
   - Use the `EX-ACT.postman_collection.json` file
   - Or click: [![Run in Postman](https://run.pstmn.io/button.svg)](https://app.getpostman.com/run-collection/7002893-9d88940d-a037-477a-b287-d42e01c25749?action=collection%2Ffork&collection-url=entityId%3D7002893-9d88940d-a037-477a-b287-d42e01c25749%26entityType%3Dcollection%26workspaceId%3D7e75d44c-4b11-4375-afea-b500866e6198)

### API Documentation

When the server is running, access the API documentation at:
- Django API Docs: http://localhost:8000/api/docs/
- Swagger UI: http://localhost:8000/api/swagger/
- ReDoc: http://localhost:8000/api/redoc/

## 🛠 Project Structure
