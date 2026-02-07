"""Utility functions and helpers."""
import warnings

def suppress_library_warnings():
    """Suppress warnings from third-party libraries like urllib3."""
    warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')
    warnings.filterwarnings('ignore', message='.*OpenSSL.*')
    warnings.filterwarnings('ignore', message='.*NotOpenSSLWarning.*')
    warnings.filterwarnings('ignore', message='.*urllib3.*')
