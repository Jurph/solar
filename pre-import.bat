@echo off
echo Cleaning up old database and migrations...
del db.sqlite3
del mysite\universe\migrations\0*.py

echo Creating fresh migrations...
python .\mysite\manage.py makemigrations

echo Applying migrations...
python .\mysite\manage.py migrate

echo Ready for import!
pause