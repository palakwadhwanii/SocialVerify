import sys

class SocialVerifyException(Exception):
    def __init__(self, error_message: str, error_detail: sys):
        self.error_message = error_message
        _, _, exc_tb = error_detail.exc_info()
        self.line_number = exc_tb.tb_lineno if exc_tb else 0
        self.file_name = exc_tb.tb_frame.f_code.co_filename if exc_tb else "unknown"
    
    def __str__(self):
        return f"Error occurred in python script [{self.file_name}] line [{self.line_number}] with error message [{self.error_message}]"

# Backwards compatibility alias
NarrativeXException = SocialVerifyException