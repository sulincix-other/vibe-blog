# Minimal Blog

A static blog generator with admin panel.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate static files
python3 generate.py

# Run server (blog + admin)
python3 main.py
```

## Admin Panel

- URL: http://localhost:8080/admin
- Login: admin / admin123

## Project Structure

```
├── src/              # Markdown source files
├── build/            # Generated static files
├── static/           # CSS, JS, images
├── templates/        # HTML templates
├── config.py         # Configuration
├── generate.py       # Static site generator
├── main.py           # Web server
└── utils.py          # Utilities
```

## Adding Posts

Create markdown files in `src/`:
- `title.md` for blog posts
- `about-lorem.md` for about page

Run `python3 generate.py` to rebuild.

## Editing Posts

Use admin panel at /admin to create/edit/delete posts.
