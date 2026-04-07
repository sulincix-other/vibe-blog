#!/usr/bin/env python3
import os
import re
import shutil
from datetime import datetime

from config import (
    SITE_TITLE, SITE_DESCRIPTION, SITE_SUBTITLE, FOOTER_TEXT,
    BUILD_DIR, POSTS_SRC, TEMPLATES_DIR, EXCERPT_LENGTH
)
from utils import get_template, render_template


def parse_markdown(md_content):
    html_parts = []
    paragraphs = []
    lines = md_content.strip().split('\n')
    in_code_block = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                html_parts.append('<pre><code>')
            else:
                html_parts.append('</code></pre>')
            continue
        
        if in_code_block:
            html_parts[-1] += '\n' + line
            continue
        
        if line.startswith('# '):
            continue
        elif line.startswith('## '):
            html_parts.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('**') and line.endswith('**'):
            html_parts.append(f'<p><strong>{line[2:-2]}</strong></p>')
            paragraphs.append(line[2:-2])
        elif line.startswith('Date:'):
            continue
        elif line.startswith('!['):
            match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if match:
                alt, src = match.groups()
                html_parts.append(f'<img src="{src}" alt="{alt}" style="max-width:100%;border-radius:8px;margin:1rem 0;">')
                continue
        else:
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
            line = re.sub(r'`(.+?)`', r'<code>\1</code>', line)
            html_parts.append(f'<p>{line}</p>')
            paragraphs.append(line.replace('<strong>', '').replace('</strong>', '').replace('<em>', '').replace('</em>', '').replace('<code>', '').replace('</code>', ''))
    
    excerpt = ' '.join(paragraphs[:2]) if paragraphs else ''
    if len(excerpt) > EXCERPT_LENGTH:
        excerpt = excerpt[:EXCERPT_LENGTH] + '...'
    return '\n            '.join(html_parts), excerpt


def generate_post(md_path, output_dir):
    with open(md_path, 'r') as f:
        md_content = f.read()
    
    title = ''
    date = ''
    
    for line in md_content.split('\n'):
        if line.startswith('# '):
            title = line[2:].strip()
        elif line.startswith('Date: '):
            date = line[6:].strip()
    
    if not date:
        mtime = os.path.getmtime(md_path)
        date = datetime.fromtimestamp(mtime).strftime('%B %d, %Y')
    
    content, excerpt = parse_markdown(md_content)
    
    slug = os.path.splitext(os.path.basename(md_path))[0].lower().replace(' ', '-')
    output_path = os.path.join(output_dir, f'{slug}.html')
    
    year = datetime.now().year
    template = get_template('post', TEMPLATES_DIR)
    html = render_template(
        template,
        title=title,
        date=date,
        content=content,
        site_title=SITE_TITLE,
        year=year,
        footer_text=FOOTER_TEXT
    )
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f'Generated: {output_path}')
    return {'title': title, 'date': date, 'slug': slug, 'excerpt': excerpt}


def generate_index(posts, output_path):
    posts_html = []
    for post in posts:
        posts_html.append(f'''<article class="post-card">
                <span class="date">{post["date"]}</span>
                <h2><a href="posts/{post["slug"]}.html">{post["title"]}</a></h2>
                <p>{post["excerpt"]}</p>
                <a href="posts/{post["slug"]}.html" class="read-more">Read more →</a>
            </article>''')
    
    year = datetime.now().year
    template = get_template('index', TEMPLATES_DIR)
    index_html = render_template(
        template,
        site_title=SITE_TITLE,
        site_description=SITE_DESCRIPTION,
        site_subtitle=SITE_SUBTITLE,
        posts='\n            '.join(posts_html),
        year=year,
        footer_text=FOOTER_TEXT
    )
    
    with open(output_path, 'w') as f:
        f.write(index_html)
    
    print(f'Generated: {output_path}')


def generate_about(build_dir):
    about_md_path = os.path.join(POSTS_SRC, '../about.md')
    if not os.path.exists(about_md_path):
        return
    
    with open(about_md_path, 'r') as f:
        md_content = f.read()
    
    title = ''
    content = parse_markdown(md_content)[0]
    
    for line in md_content.split('\n'):
        if line.startswith('# '):
            title = line[2:].strip()
    
    template_path = os.path.join(TEMPLATES_DIR, 'about.html')
    if not os.path.exists(template_path):
        return
    
    with open(template_path, 'r') as f:
        template = f.read()
    
    year = datetime.now().year
    html = render_template(
        template,
        title=title,
        content=content,
        site_title=SITE_TITLE,
        year=year,
        footer_text=FOOTER_TEXT
    )
    
    output_path = os.path.join(build_dir, 'about.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f'Generated: {output_path}')


def main():
    build_dir = BUILD_DIR
    posts_dir = os.path.join(build_dir, 'posts')
    posts_src = POSTS_SRC
    
    os.makedirs(posts_dir, exist_ok=True)
    os.makedirs(posts_src, exist_ok=True)
    
    static_css = 'static/styles.css'
    if os.path.exists(static_css):
        shutil.copy(static_css, build_dir)
        print(f'Copied: {static_css} -> {build_dir}')
    
    posts = []
    for filename in os.listdir(posts_src):
        if filename.endswith('.md') and filename != 'about-lorem.md':
            path = os.path.join(posts_src, filename)
            post = generate_post(path, posts_dir)
            posts.append(post)
    
    posts.sort(key=lambda x: x['date'], reverse=True)
    generate_index(posts, os.path.join(build_dir, 'index.html'))
    generate_about(build_dir)
    
    print(f'\nDone! Generated {len(posts)} posts to {build_dir}/')


if __name__ == '__main__':
    main()
