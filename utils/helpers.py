#!/usr/bin/python3
# -*- coding: utf-8 -*-

import unicodedata
import string
import logging

# Valid characters for filenames
valid_filename_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
char_limit = 255

def clean_filename(filename, whitelist=valid_filename_chars, replace=' '):
    """
    Clean a filename to ensure it only contains valid characters.
    
    Args:
        filename (str): The filename to clean
        whitelist (str): Characters to allow in the filename
        replace (str): Characters to replace with underscore
        
    Returns:
        str: Cleaned filename
    """
    # replace spaces
    for r in replace:
        filename = filename.replace(r,'_')
    
    # keep only valid ascii chars
    cleaned_filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    
    # keep only whitelisted chars
    cleaned_filename = ''.join(c for c in cleaned_filename if c in whitelist)
    if len(cleaned_filename) > char_limit:
        logging.warn(f"Warning, filename truncated because it was over {char_limit}. Filenames may no longer be unique")
    return cleaned_filename[:char_limit]

def format_date(iso_date):
    """
    Convert ISO date to YYYY-MM-DD format.
    
    Args:
        iso_date (str): ISO format date string
        
    Returns:
        str: Date in YYYY-MM-DD format or 'unknown_date' if None
    """
    return iso_date.split('T')[0] if iso_date else 'unknown_date'
