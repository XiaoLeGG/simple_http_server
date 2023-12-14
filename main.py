from HTTPServer import HTTPServer
from HTTPRequest import HTTPRequest
from HTTPResponse import HTTPResponse

import utils
import argparse

def generate_test_accounts():
    try:
        utils.create_user("test", "test")
        utils.create_user("test2", "test2")
        utils.create_user("test3", "test3")
    except Exception as e:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    
    generate_test_accounts()
    server = HTTPServer()
    server.run()