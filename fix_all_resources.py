import re

# Input HTML file
input_file = "index.html"

# Output HTML file (Flask-ready)
output_file = "templates/index.html"

# Read original HTML
with open(input_file, 'r', encoding='utf-8') as f:
    html = f.read()

# -----------------------------
# Fix CSS <link> tags
# -----------------------------
css_pattern = r'<link\s+.*?href="(.*?)".*?>'
def replace_css(match):
    filename = match.group(1).split('/')[-1]
    return f'<link rel="stylesheet" href="{{{{ url_for(\'static\', filename=\'css/{filename}\') }}}}">'

html = re.sub(css_pattern, replace_css, html)

# -----------------------------
# Fix JS <script> tags
# -----------------------------
js_pattern = r'<script\s+.*?src="(.*?)".*?></script>'
def replace_js(match):
    filename = match.group(1).split('/')[-1]
    return f'<script src="{{{{ url_for(\'static\', filename=\'js/{filename}\') }}}}"></script>'

html = re.sub(js_pattern, replace_js, html)

# -----------------------------
# Fix Squarespace <img> tags
# -----------------------------
def fix_img_tag(match):
    tag = match.group(0)

    # Extract first src
    src_match = re.search(r'src="([^"]+)"', tag)
    if not src_match:
        return tag
    filename = src_match.group(1).split('/')[-1].split('?')[0]

    new_src = f'{{{{ url_for(\'static\', filename=\'images/{filename}\') }}}}'

    # Fix srcset
    srcset_match = re.search(r'srcset="([^"]+)"', tag)
    new_srcset_str = ''
    if srcset_match:
        srcset_entries = srcset_match.group(1).split(',')
        new_srcset = []
        for entry in srcset_entries:
            parts = entry.strip().split(' ')
            file_path = parts[0].split('/')[-1].split('?')[0]
            query = '?' + parts[0].split('?')[1] if '?' in parts[0] else ''
            size = parts[1] if len(parts) > 1 else ''
            new_srcset.append(f'{{{{ url_for(\'static\', filename=\'images/{file_path}\') }}}}{query} {size}'.strip())
        new_srcset_str = ', '.join(new_srcset)

    # Remove all duplicate src and alt
    tag = re.sub(r'(src|alt)="[^"]+"', '', tag[1:-1])

    # Add correct src and alt
    alt_match = re.search(r'alt="([^"]*)"', match.group(0))
    alt_text = alt_match.group(1) if alt_match else filename
    fixed_tag = f'<img src="{new_src}" alt="{alt_text}"'

    # Preserve other attributes (width, height, style, class, id, sizes, loading, decoding, data-*)
    attrs = re.findall(r'(width|height|style|sizes|loading|decoding|class|id|data-[^=]+)="([^"]+)"', match.group(0))
    for key, val in attrs:
        fixed_tag += f' {key}="{val}"'

    if srcset_match:
        fixed_tag += f' srcset="{new_srcset_str}"'

    fixed_tag += '>'
    return fixed_tag

html = re.sub(r'<img[^>]+>', fix_img_tag, html)

# -----------------------------
# Save output
# -----------------------------
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"All CSS, JS, and image paths fixed! Output saved to {output_file}")
