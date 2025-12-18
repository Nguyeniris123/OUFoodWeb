#!/bin/bash
set -e

echo "Waiting for MySQL to be ready..."

# Sử dụng để check MySQL connection
python << END
import time
import sys
import pymysql
import os

max_retries = 10
retry_count = 0

while retry_count < max_retries:
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=int(os.getenv('DB_PORT', 3306)),
            connect_timeout=5
        )
        conn.close()
        print("✓ MySQL is up and running!")
        sys.exit(0)
    except Exception as e:
        retry_count += 1
        print(f"MySQL is unavailable (attempt {retry_count}/{max_retries}) - {str(e)}")
        print(os.getenv('DB_HOST'))
        print(os.getenv('DB_NAME'))
        time.sleep(2)

print("Failed to connect to MySQL after maximum retries")
sys.exit(1)
END

if [ $? -ne 0 ]; then
    echo "MySQL connection failed!"
    exit 1
fi

echo "Running database migrations..."
flask db upgrade

if [ $? -eq 0 ]; then
  echo "Migrations completed!"
else
  echo "Migrations failed!"
  exit 1
fi

echo " Starting application..."
exec "$@"