from http_server import HTTPServer
from http_request import HTTPRequest
from http_response import HTTPResponse

import utils
import argparse

def generate_account(user, password):
    try:
        utils.create_user(user, password)
    except Exception as e:
        pass

def generate_test_accounts():
    generate_account("client1", "123")
    generate_account("client2", "123")
    generate_account("client3", "123")


if __name__ == "__main__":
    utils.init_sql()
    generate_test_accounts()
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--ip", type=str, default="localhost", help="Server IP address")
    parser.add_argument("-p", "--port", type=int, default=8080, help="Server port number")
    parser.add_argument("--parallel", type=int, default=5, help="Number of parallel connections")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout seconds for keep-alive connections") 
    parser.add_argument("-c", "--cookie-persist-time", type=int, default=3600, help="Cookie persist time in seconds")
    parser.add_argument("-d", "--debug", type=bool, help="Debug mode")
    parser.add_argument("-s", "--server", type=str, default="CS305 HTTP Server/1.0", help="Server name")
    args = parser.parse_args()
    server = HTTPServer(host=args.ip, port=args.port, parallel=args.parallel, timeout=args.timeout, cookie_persist_time=args.cookie_persist_time, debug=args.debug, server=args.server)
    server.run()