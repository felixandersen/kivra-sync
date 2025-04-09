#!/usr/bin/python3
# -*- coding: utf-8 -*-

import io
import logging
import html
from weasyprint import HTML

# Configure weasyprint logging
logger = logging.getLogger('weasyprint')
logger.setLevel(logging.ERROR)
logger.handlers = [logging.FileHandler('./weasyprint.log')]  # Remove the default stderr handler

def text_to_html(text_content, title=None):
    """
    Convert plain text to HTML with a clean, readable template.
    
    Args:
        text_content (str): Plain text content to convert
        title (str, optional): Title to display in the HTML
        
    Returns:
        str: HTML content
    """
    # Escape HTML special characters
    escaped_text = html.escape(text_content)
    
    # Replace newlines with <br> tags and preserve whitespace
    formatted_text = escaped_text.replace('\n', '<br>')
    
    # Create HTML with a clean template
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title or 'Document'}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 2cm;
            color: #333;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        .header {{
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .content {{
            white-space: pre-wrap;
            font-family: monospace;
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 0.8em;
            color: #777;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title or 'Document'}</h1>
        </div>
        <div class="content">
{formatted_text}
        </div>
        <div class="footer">
            Converted from plain text
        </div>
    </div>
</body>
</html>"""
    
    return html_content

def html_to_pdf(html_content):
    """
    Convert HTML content to PDF.
    
    Args:
        html_content (str): HTML content to convert
        
    Returns:
        bytes: PDF content as bytes, or None if conversion failed
    """
    try:
        pdf_buffer = io.BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()
    except Exception as e:
        logging.error(f"Error converting HTML to PDF: {str(e)}")
        return None
