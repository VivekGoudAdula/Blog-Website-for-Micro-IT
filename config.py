import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    MYSQL_HOST = 'localhost' # Hardcode for test
    MYSQL_USER = 'root'      # Hardcode for test
    MYSQL_PASSWORD = 'Vivvi#2405' # Hardcode with the EXACT password you set in MySQL
    MYSQL_DB = 'blog_db'     # Hardcode for test
    MYSQL_CURSORCLASS = 'DictCursor' # Optional: to return results as dictionaries 