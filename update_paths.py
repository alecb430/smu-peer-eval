import re


input_file = "index.html"


output_file = "templates/index.html"


css_pattern = r'<link\s+.*?href="(.*?)".*?>'
js_pattern = r'<script\s+.*?src="(.*?)".*?></script>'
img_pattern = r'<img\s+.*?src="(.*?)"(.*?)>'


def replace_css(match):
    filename = match.group(1).split('/')[-1]
    return f'<link rel="stylesheet" href="{{{{ url_for(\'static\', filename=\'css/{filename}\') }}}}">'

def replace_js(match):
    filename = match.group(1).split('/')[-1]
    return f'<script src="{{{{ url_for(\'static\', filename=\'js/{filename}\') }}}}"></script>'

def replace_img(match):
    filename = match.group(1).split('/')[-1]
    rest = match.group(2)
    return f'<img src="{{{{ url_for(\'static\', filename=\'images/{filename}\') }}}}"{rest}>'


with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()


content = re.sub(css_pattern, replace_css, content)
content = re.sub(js_pattern, replace_js, content)
content = re.sub(img_pattern, replace_img, content)


with open(output_file, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"HTML paths updated! Output saved to {output_file}")