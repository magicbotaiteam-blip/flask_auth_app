FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Accept Google OAuth credentials as build args for production
ARG GOOGLE_CLIENT_ID
ARG GOOGLE_CLIENT_SECRET
ENV GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
ENV GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
ENV OAUTHLIB_INSECURE_TRANSPORT=false
ENV SKIP_DOTENV=1

# S3 bucket for persistent file storage
ARG S3_BUCKET_NAME=flask-auth-app-uploads
ENV S3_BUCKET_NAME=$S3_BUCKET_NAME

# PostgreSQL connection string (set via SSM or ECS env)
# Example: postgresql://username:password@host:5432/flask_auth_app
ENV DATABASE_URL=

# Expose port 80 (Express Mode ALB expects port 80)
EXPOSE 80

# Run the production app
CMD ["python", "app_complete_with_groups.py"]
