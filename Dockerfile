# Giai đoạn 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Giai đoạn 2: Sản phẩm cuối cùng
FROM python:3.11-slim

# Tạo user mới
RUN useradd -m -u 1000 appuser

# ĐẶT WORKDIR TRƯỚC KHI COPY
WORKDIR /app

# Copy thư viện Python từ builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy source code vào /app
COPY --chown=appuser:appuser . .

# Copy entrypoint script và set quyền thực thi
COPY --chown=appuser:appuser migrations /app/migrations

# Set quyền cho entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh


# Set PATH và PYTHONPATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app


# Chuyển sang user appuser
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app/index.py"]