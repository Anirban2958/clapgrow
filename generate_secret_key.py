#!/usr/bin/env python3
"""
Generate a secure SECRET_KEY for Flask applications
Usage: python generate_secret_key.py
"""

import secrets
import string

def generate_secret_key(length=64):
    """Generate a cryptographically secure secret key."""
    # Method 1: Hexadecimal (most common)
    hex_key = secrets.token_hex(length // 2)
    
    # Method 2: URL-safe base64
    urlsafe_key = secrets.token_urlsafe(length)
    
    # Method 3: Custom alphabet
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    custom_key = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    print("=" * 70)
    print("🔑 SECRET KEY GENERATOR")
    print("=" * 70)
    print("\n📌 Hexadecimal (Recommended):")
    print(hex_key)
    print("\n📌 URL-Safe Base64:")
    print(urlsafe_key)
    print("\n📌 Custom Characters:")
    print(custom_key)
    print("\n" + "=" * 70)
    print("💡 Copy any one of these to your .env or Render dashboard")
    print("=" * 70)

if __name__ == "__main__":
    generate_secret_key()
