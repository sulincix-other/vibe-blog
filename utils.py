import os


def get_template(name, templates_dir):
    path = os.path.join(templates_dir, f'{name}.html')
    with open(path, 'r') as f:
        return f.read()


def render_template(template, **kwargs):
    for key, value in kwargs.items():
        template = template.replace(f'[[{key}]]', str(value))
    return template
