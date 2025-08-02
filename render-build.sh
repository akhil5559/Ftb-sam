#!/usr/bin/env bash
# Install system dependencies for Tesseract
apt-get update && apt-get install -y tesseract-ocr
pip install -r requirements.txt
