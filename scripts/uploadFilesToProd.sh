#!/bin/bash
# upload all files from a bot's user directory to S3
# Depends on AWS credentials being set via environment variables or ~/.aws/credentials.

if [ $# -lt 2 ]; then
  echo "usage: $0 username botname"
  echo "uploads all files from ~/Documents/openclawUsers/username/botname/ to S3"
  exit 1
fi

SRC_DIR="/Users/siyang/Documents/openclawUsers/$1/$2"
DST_DIR="s3://flask-auth-app-uploads/bots/$1/$2/"

echo "Uploading all files from $SRC_DIR to $DST_DIR"
aws s3 cp "$SRC_DIR/" "$DST_DIR" --recursive
