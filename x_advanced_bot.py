"""Backward-compatible entry point for the official X API manager.

Legacy Selenium cookie injection (X_AUTH_TOKEN/X_CT0) has been removed.
Use OAuth 2.0 user-context credentials and x_follow_manager.py instead.
"""
from x_follow_manager import run


if __name__ == "__main__":
    run()
