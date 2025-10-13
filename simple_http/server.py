import socket
import os
import mimetypes
from datetime import datetime

# Configuration
HOST = '0.0.0.0'
PORT = 8080
SERVER_ROOT = os.path.expanduser('~/simple_http/www')
POST_DATA_FILE = os.path.expanduser('~/simple_http/post_data.txt')
BUFFER_SIZE = 4096

# Initialize mimetypes
mimetypes.init()

def parse_request(raw_request):
    """
    Parse raw HTTP request into components.
    Returns: (method, path, version, headers_dict, body)
    """
    try:
        # Split headers and body
        if b'\r\n\r\n' in raw_request:
            header_part, body = raw_request.split(b'\r\n\r\n', 1)
        else:
            header_part = raw_request
            body = b''
        
        # Decode headers
        header_text = header_part.decode('utf-8', errors='ignore')
        lines = header_text.split('\r\n')
        
        # Parse request line
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) != 3:
            return None, None, None, None, None
        
        method, path, version = parts
        
        # Parse headers into dictionary
        headers = {}
        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
        return method, path, version, headers, body
    except Exception as e:
        print(f"Error parsing request: {e}")
        return None, None, None, None, None

def resolve_path(http_path):
    """
    Convert HTTP path to filesystem path.
    Handles default index.html and prevents directory traversal.
    """
    # Remove query string if present
    if '?' in http_path:
        http_path = http_path.split('?')[0]
    
    # Default to index.html for root
    if http_path == '/':
        http_path = '/index.html'
    
    # Remove leading slash
    relative_path = http_path.lstrip('/')
    
    # Prevent directory traversal
    if '..' in relative_path:
        return None
    
    # Join with server root
    full_path = os.path.join(SERVER_ROOT, relative_path)
    return full_path

def get_mime_type(filepath):
    """
    Determine MIME type based on file extension.
    """
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type or 'application/octet-stream'

def build_response(status_code, reason, headers, body=b''):
    """
    Build complete HTTP response with status line, headers, and body.
    """
    # Status line
    status_line = f"HTTP/1.1 {status_code} {reason}\r\n"
    
    # Build headers
    header_lines = []
    for key, value in headers.items():
        header_lines.append(f"{key}: {value}\r\n")
    
    # Combine all parts
    response = status_line.encode('utf-8')
    for header in header_lines:
        response += header.encode('utf-8')
    response += b'\r\n'  # Empty line between headers and body
    response += body
    
    return response

def handle_get(path, headers):
    """
    Handle GET request - return file content if exists, 404 otherwise.
    """
    filepath = resolve_path(path)
    
    if filepath is None or not os.path.isfile(filepath):
        # File not found
        body = b'404 Not Found'
        response_headers = {
            'Content-Type': 'text/html',
            'Content-Length': str(len(body)),
            'Connection': 'close'
        }
        return build_response(404, 'Not Found', response_headers, body)
    
    # Read file content
    try:
        with open(filepath, 'rb') as f:
            body = f.read()
        
        mime_type = get_mime_type(filepath)
        response_headers = {
            'Content-Type': mime_type,
            'Content-Length': str(len(body)),
            'Connection': 'close'
        }
        return build_response(200, 'OK', response_headers, body)
    except Exception as e:
        print(f"Error reading file: {e}")
        body = b'500 Internal Server Error'
        response_headers = {
            'Content-Type': 'text/html',
            'Content-Length': str(len(body)),
            'Connection': 'close'
        }
        return build_response(500, 'Internal Server Error', response_headers, body)

def handle_post(path, headers, body):
    """
    Handle POST request - only allowed at /post, append to post_data.txt.
    """
    if path != '/post':
        return handle_unsupported('POST')
    
    # Append body to post_data.txt with timestamp
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(POST_DATA_FILE, 'a') as f:
            f.write(f"\n[{timestamp}]\n")
            f.write(body.decode('utf-8', errors='ignore'))
            f.write('\n')
        
        response_body = b'POST received and stored.'
        response_headers = {
            'Content-Type': 'text/plain',
            'Content-Length': str(len(response_body)),
            'Connection': 'close'
        }
        return build_response(200, 'OK', response_headers, response_body)
    except Exception as e:
        print(f"Error handling POST: {e}")
        body = b'500 Internal Server Error'
        response_headers = {
            'Content-Type': 'text/html',
            'Content-Length': str(len(body)),
            'Connection': 'close'
        }
        return build_response(500, 'Internal Server Error', response_headers, body)

def handle_put(path, headers, body):
    """
    Handle PUT request - write body to target file, create if needed.
    """
    # Remove leading slash and construct full path
    relative_path = path.lstrip('/')
    
    # Prevent directory traversal
    if '..' in relative_path:
        response_body = b'400 Bad Request'
        response_headers = {
            'Content-Type': 'text/plain',
            'Content-Length': str(len(response_body)),
            'Connection': 'close'
        }
        return build_response(400, 'Bad Request', response_headers, response_body)
    
    # Full filepath (relative to home directory for PUT)
    base_dir = os.path.expanduser('~/simple_http')
    full_path = os.path.join(base_dir, relative_path)
    
    # Check if file exists (to determine status code)
    file_exists = os.path.isfile(full_path)
    
    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write body to file
        with open(full_path, 'wb') as f:
            f.write(body)
        
        # Extract filename for response
        filename = os.path.basename(full_path)
        
        if file_exists:
            response_body = f'PUT stored as {filename}'.encode('utf-8')
            response_headers = {
                'Content-Type': 'text/plain',
                'Content-Length': str(len(response_body)),
                'Connection': 'close'
            }
            return build_response(200, 'OK', response_headers, response_body)
        else:
            response_body = f'PUT stored as {filename}'.encode('utf-8')
            response_headers = {
                'Content-Type': 'text/plain',
                'Content-Length': str(len(response_body)),
                'Location': path,
                'Connection': 'close'
            }
            return build_response(201, 'Created', response_headers, response_body)
    except Exception as e:
        print(f"Error handling PUT: {e}")
        body = b'500 Internal Server Error'
        response_headers = {
            'Content-Type': 'text/html',
            'Content-Length': str(len(body)),
            'Connection': 'close'
        }
        return build_response(500, 'Internal Server Error', response_headers, body)

def handle_head(path, headers):
    """
    Handle HEAD request - same as GET but return only headers, no body.
    """
    filepath = resolve_path(path)
    
    if filepath is None or not os.path.isfile(filepath):
        # File not found
        response_headers = {
            'Content-Type': 'text/html',
            'Content-Length': '14',  # Length of "404 Not Found"
            'Connection': 'close'
        }
        return build_response(404, 'Not Found', response_headers, b'')
    
    try:
        # Get file size without reading content
        file_size = os.path.getsize(filepath)
        mime_type = get_mime_type(filepath)
        
        response_headers = {
            'Content-Type': mime_type,
            'Content-Length': str(file_size),
            'Connection': 'close'
        }
        return build_response(200, 'OK', response_headers, b'')
    except Exception as e:
        print(f"Error handling HEAD: {e}")
        response_headers = {
            'Content-Type': 'text/html',
            'Content-Length': '26',
            'Connection': 'close'
        }
        return build_response(500, 'Internal Server Error', response_headers, b'')

def handle_unsupported(method):
    """
    Handle unsupported HTTP methods.
    """
    body = b'Method Not Allowed'
    response_headers = {
        'Content-Type': 'text/plain',
        'Allow': 'GET, POST, PUT, HEAD',
        'Content-Length': str(len(body)),
        'Connection': 'close'
    }
    return build_response(405, 'Method Not Allowed', response_headers, body)

def handle_request(method, path, version, headers, body):
    """
    Route request to appropriate handler based on method.
    """
    print(f"Request: {method} {path}")
    
    if method == 'GET':
        return handle_get(path, headers)
    elif method == 'POST':
        return handle_post(path, headers, body)
    elif method == 'PUT':
        return handle_put(path, headers, body)
    elif method == 'HEAD':
        return handle_head(path, headers)
    else:
        return handle_unsupported(method)

def start_server():
    """
    Main server loop - create socket, bind, listen, and handle connections.
    """
    # Create TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Allow socket reuse
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind to address and port
    server_socket.bind((HOST, PORT))
    
    # Listen for connections
    server_socket.listen(5)
    
    print(f"Server listening on {HOST}:{PORT}")
    print(f"Server root: {SERVER_ROOT}")
    print("Press Ctrl+C to stop the server\n")
    
    try:
        while True:
            # Accept client connection
            client_socket, client_address = server_socket.accept()
            print(f"Connection from {client_address}")
            
            try:
                # Receive request data
                raw_request = b''
                while True:
                    chunk = client_socket.recv(BUFFER_SIZE)
                    raw_request += chunk
                    
                    # Check if we have complete headers
                    if b'\r\n\r\n' in raw_request:
                        # Parse to check for Content-Length
                        method, path, version, headers, partial_body = parse_request(raw_request)
                        
                        if method in ['POST', 'PUT'] and 'content-length' in headers:
                            content_length = int(headers['content-length'])
                            # Calculate how much body we already have
                            body_start = raw_request.index(b'\r\n\r\n') + 4
                            current_body_length = len(raw_request) - body_start
                            
                            # Read remaining body if needed
                            while current_body_length < content_length:
                                chunk = client_socket.recv(BUFFER_SIZE)
                                if not chunk:
                                    break
                                raw_request += chunk
                                current_body_length += len(chunk)
                        break
                    
                    if not chunk:
                        break
                
                # Parse request
                method, path, version, headers, body = parse_request(raw_request)
                
                if method is None:
                    # Bad request
                    response = build_response(400, 'Bad Request', 
                                            {'Content-Length': '11', 'Connection': 'close'}, 
                                            b'Bad Request')
                else:
                    # Handle request
                    response = handle_request(method, path, version, headers, body)
                
                # Send response
                client_socket.sendall(response)
                
            except Exception as e:
                print(f"Error handling request: {e}")
            finally:
                # Close client connection
                client_socket.close()
                
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server_socket.close()

if __name__ == '__main__':
    start_server()