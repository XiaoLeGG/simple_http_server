from datetime import datetime
import os
import enum

class LogLevel(enum.Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    FATAL = 4

class Log:
    def __init__(self, log_file : str, print_to_os : bool=True):
        self.log_file = log_file
        self.print_to_os = print_to_os
        if not self.log_file.endswith('.log'):
            self.log_file += '.log'
        
        if not os.path.exists(self.log_file):
            dir = os.path.dirname(self.log_file)
            if not os.path.exists(dir):
                os.makedirs(dir)
            with open(self.log_file, 'w') as f:
                f.write('')

    def format_message(self, type : LogLevel, message : str):
        current_time = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{ type.name }][{current_time}] {message}"
        return formatted_message

    def log(self, type : LogLevel, message : str):
        formatted_message = self.format_message(type, message)
        if self.print_to_os:
            print(formatted_message)
        with open(self.log_file, 'a') as f:
            f.write(formatted_message + '\n')
