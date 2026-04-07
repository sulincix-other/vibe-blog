import os
import re
import http.server
import socketserver
import json
import subprocess
from urllib.parse import urlparse, parse_qs

from config import *

def get_md_title(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        for line in f:
            if line.startswith("# "):
                return line[2:].strip()
    return ""


def get_md_date(path):
    if not os.path.exists(path):
        return ""
    mtime = os.path.getmtime(path)
    from datetime import datetime
    return datetime.fromtimestamp(mtime).strftime('%B %d, %Y')


def read_md_body(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip() == "" and i > 0:
            return "".join(lines[i:]).strip()
    return ""


def generate_blog():
    subprocess.run(["python3", "generate.py"], capture_output=True)


class BlogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/":
            self.serve_build_file("index.html")
            return
        
        if path.startswith("/static/"):
            self.serve_static(path)
            return
        
        if path == "/admin" or path == "/admin/":
            self.serve_file("templates/admin/login.html", "text/html")
            return
        
        if path == "/admin/login.html":
            self.serve_file("templates/admin/login.html", "text/html")
            return
        
        if path == "/admin/dashboard.html":
            if not self.is_logged_in():
                self.send_response(302)
                self.send_header("Location", "/admin")
                self.end_headers()
                return
            self.serve_admin_page()
            return
        
        if path.startswith("/admin/posts/"):
            if not self.is_logged_in():
                self.send_response(302)
                self.send_header("Location", "/admin")
                self.end_headers()
                return
            
            if path == "/admin/posts/edit.html":
                query = parse_qs(parsed.query)
                slug = query.get("slug", [""])[0]
                self.serve_post_form(slug)
                return
        
        if path == "/api/posts":
            if not self.is_logged_in():
                self.send_error(401)
                return
            self.send_json_response(self.get_posts())
            return
        
        if path == "/api/generate":
            if not self.is_logged_in():
                self.send_error(401)
                return
            generate_blog()
            self.send_json_response({"success": True})
            return
        
        self.serve_build_file(path.lstrip("/"))
    
    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/api/login":
            self.handle_login()
            return
        
        if parsed.path == "/api/logout":
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.send_header("Set-Cookie", "session=; Path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.end_headers()
            return
        
        if parsed.path == "/api/posts":
            if not self.is_logged_in():
                self.send_error(401)
                return
            self.handle_post_create()
            return
        
        if parsed.path == "/api/posts/update":
            if not self.is_logged_in():
                self.send_error(401)
                return
            self.handle_post_update()
            return
        
        if parsed.path == "/api/posts/delete":
            if not self.is_logged_in():
                self.send_error(401)
                return
            self.handle_post_delete()
            return
        
        if parsed.path == "/api/upload":
            if not self.is_logged_in():
                self.send_error(401)
                return
            self.handle_upload()
            return
    
    def handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        
        if "multipart/form-data" in content_type:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            
            boundary = content_type.split("boundary=")[-1]
            parts = body.split(b"--" + boundary.encode())
            
            for part in parts:
                if b"Content-Disposition" in part and b"filename=" in part:
                    filename_match = re.search(b'filename="([^"]+)"', part)
                    if filename_match:
                        filename = filename_match.group(1).decode()
                        
                        # Security: validate filename
                        if ".." in filename or "/" in filename or "\\" in filename:
                            self.send_error(400)
                            return
                        
                        data_match = re.search(b'\r\n\r\n(.+)$', part, re.DOTALL)
                        if data_match:
                            image_data = data_match.group(1)
                            
                            img_dir = os.path.join(BUILD_DIR, "images")
                            os.makedirs(img_dir, exist_ok=True)
                            
                            # Security: only allow safe filename chars
                            safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
                            
                            # Security: validate final path is within images dir
                            filepath = os.path.join(img_dir, safe_name)
                            real_path = os.path.realpath(filepath)
                            real_img_dir = os.path.realpath(img_dir)
                            if not real_path.startswith(real_img_dir):
                                self.send_error(403)
                                return
                            
                            with open(filepath, "wb") as f:
                                f.write(image_data)
                            
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(json.dumps({"success": True, "url": f"/images/{safe_name}", "name": filename}).encode())
                            return
        
        self.send_error(400)
    
    def serve_static(self, path):
        # Security: prevent path traversal
        path = path.lstrip("/")
        if ".." in path or path.startswith("/"):
            self.send_error(403)
            return
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(base_dir, path)
        
        # Ensure filepath is within base_dir
        real_path = os.path.realpath(filepath)
        if not real_path.startswith(os.path.realpath(base_dir)):
            self.send_error(403)
            return
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            content_type = "text/css"
            if path.endswith(".js"):
                content_type = "application/javascript"
            elif path.endswith(".svg"):
                content_type = "image/svg+xml"
            elif path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                content_type = "image/" + path.rsplit(".", 1)[1]
                if content_type == "image/jpg":
                    content_type = "image/jpeg"
            
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)
    
    def serve_build_file(self, filename):
        # Security: prevent path traversal
        if ".." in filename or filename.startswith("/"):
            self.send_error(403)
            return
        
        filepath = os.path.join(BUILD_DIR, filename)
        
        # Ensure filepath is within BUILD_DIR
        real_path = os.path.realpath(filepath)
        real_build = os.path.realpath(BUILD_DIR)
        if not real_path.startswith(real_build):
            self.send_error(403)
            return
        
        if os.path.isdir(filepath):
            filepath = os.path.join(filepath, "index.html")
        
        if os.path.exists(filepath):
            content_type = "text/html"
            if filepath.endswith(".css"):
                content_type = "text/css"
            elif filepath.endswith(".js"):
                content_type = "application/javascript"
            
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)
    
    def is_logged_in(self):
        cookie = self.headers.get("Cookie", "")
        return "session=admin" in cookie
    
    def get_posts(self):
        posts = []
        if os.path.exists(POSTS_SRC):
            for fname in sorted(os.listdir(POSTS_SRC), reverse=True):
                if fname.endswith(".md"):
                    slug = fname[:-3]
                    path = os.path.join(POSTS_SRC, fname)
                    posts.append({
                        "slug": slug,
                        "title": get_md_title(path),
                        "date": get_md_date(path)
                    })
        return posts
    
    def serve_file(self, filepath, content_type):
        # Security: prevent path traversal
        if ".." in filepath or not os.path.isabs(filepath):
            real_path = os.path.realpath(filepath)
            base_dir = os.path.dirname(os.path.abspath(__file__))
            if not real_path.startswith(os.path.realpath(base_dir)):
                self.send_error(403)
                return
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)
    
    def serve_admin_page(self):
        posts = self.get_posts()
        
        template_path = os.path.join(os.path.dirname(__file__), "templates/admin/dashboard.html")
        with open(template_path, "r") as f:
            template = f.read()
        
        posts_html = ""
        for post in posts:
            posts_html += f'''
                <tr>
                    <td>{post["title"]}</td>
                    <td>{post["date"]}</td>
                    <td class="actions">
                        <a href="/posts/{post["slug"]}.html" target="_blank" class="btn">Show</a>
                        <a href="/admin/posts/edit.html?slug={post["slug"]}" class="btn">Edit</a>
                        <button onclick="deletePost('{post["slug"]}')" class="btn btn-danger">Delete</button>
                    </td>
                </tr>'''
        
        if not posts:
            posts_html = '<tr><td colspan="3" style="text-align: center;">No posts</td></tr>'
        
        html = template.replace("{{posts}}", posts_html)
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_post_form(self, slug):
        template_path = os.path.join(os.path.dirname(__file__), "templates/admin/post_form.html")
        with open(template_path, "r") as f:
            template = f.read()
        
        is_edit = bool(slug and os.path.exists(os.path.join(POSTS_SRC, f"{slug}.md")))
        
        if is_edit:
            path = os.path.join(POSTS_SRC, f"{slug}.md")
            post_title = get_md_title(path)
            post_content = read_md_body(path)
            title = "Edit Post"
            button_text = "Update Post"
        else:
            post_title = ""
            post_content = ""
            title = "New Post"
            button_text = "Create Post"
        
        html = (template
            .replace("{{slug}}", slug or "")
            .replace("{{title}}", title)
            .replace("{{post_title}}", post_title)
            .replace("{{post_content}}", post_content)
            .replace("{{button_text}}", button_text))
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def handle_login(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        data = json.loads(body)
        
        if data.get("username") == ADMIN_USER and data.get("password") == ADMIN_PASS:
            self.send_response(200)
            self.send_header("Set-Cookie", "session=admin; Path=/")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        else:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False}).encode())
    
    def handle_post_create(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        data = json.loads(body)
        
        title = data.get("title", "")
        content = data.get("content", "")
        slug = re.sub(r'[^a-z0-9-]', '-', title.lower().replace(" ", "-"))
        
        md = f"# {title}\n\n{content}"
        
        path = os.path.join(POSTS_SRC, f"{slug}.md")
        with open(path, "w") as f:
            f.write(md)
        
        generate_blog()
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "slug": slug}).encode())
    
    def handle_post_update(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        data = json.loads(body)
        
        slug = data.get("slug", "")
        title = data.get("title", "")
        content = data.get("content", "")
        
        md = f"# {title}\n\n{content}"
        
        path = os.path.join(POSTS_SRC, f"{slug}.md")
        with open(path, "w") as f:
            f.write(md)
        
        generate_blog()
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode())
    
    def handle_post_delete(self):
        slug = parse_qs(urlparse(self.path).query).get("slug", [""])[0]
        
        path = os.path.join(POSTS_SRC, f"{slug}.md")
        if os.path.exists(path):
            os.remove(path)
        
        generate_blog()
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode())
    
    def send_json_response(self, data):
        json_str = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(json_str))
        self.end_headers()
        self.wfile.write(json_str.encode())


os.makedirs(POSTS_SRC, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

generate_blog()

class ReuseAddrTCPServer(socketserver.TCPServer):
    def server_bind(self):
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()

with ReuseAddrTCPServer(("", PORT), BlogHandler) as httpd:
    print(f"Blog: http://localhost:{PORT}/")
    print(f"Admin: http://localhost:{PORT}/admin")
    httpd.serve_forever()
