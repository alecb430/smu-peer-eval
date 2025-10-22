import re

# Input HTML file (original Squarespace export)
input_file = "index.html"

# Output HTML file (Flask-ready)
output_file = "templates/index.html"

# Read the HTML
with open(input_file, 'r', encoding='utf-8') as f:
    html = f.read()


# Regex to fix <img> tags
def fix_img_tag(match):
    tag = match.group(0)

    # Extract filename from first src (ignore duplicates)
    src_match = re.search(r'src="([^"]+)"', tag)
    if not src_match:
        return tag  # no src found, leave tag as is
    filename = src_match.group(1).split('/')[-1].split('?')[0]  # get only filename without query

    # Build new src
    new_src = f'{{{{ url_for(\'static\', filename=\'images/{filename}\') }}}}'

    # Fix srcset if it exists
    srcset_match = re.search(r'srcset="([^"]+)"', tag)
    if srcset_match:
        srcset_entries = srcset_match.group(1).split(',')
        new_srcset = []
        for entry in srcset_entries:
            parts = entry.strip().split(' ')
            file_path = parts[0].split('/')[-1].split('?')[0]
            size = parts[1] if len(parts) > 1 else ''
            new_srcset.append(
                f'{{{{ url_for(\'static\', filename=\'images/{file_path}\') }}}}?{parts[0].split("?")[1] if "?" in parts[0] else ""} {size}'.strip())
        new_srcset_str = ', '.join(new_srcset)
        tag = re.sub(r'srcset="[^"]+"', f'srcset="{new_srcset_str}"', tag)

    # Replace the first src
    tag = re.sub(r'src="[^"]+"', f'src="{new_src}"', tag, count=1)

    # Remove duplicate src and alt attributes
    tag = re.sub(r'(src|alt)="[^"]+"', '', tag[1:-1])  # remove all src/alt
    # Add correct src and alt
    alt_match = re.search(r'alt="([^"]*)"', match.group(0))
    alt_text = alt_match.group(1) if alt_match else filename
    fixed_tag = f'<img src="{new_src}" alt="{alt_text}"'

    # Preserve width, height, style, and other attributes
    attrs = re.findall(r'(width|height|style|sizes|loading|decoding|class|id|data-[^=]+)="([^"]+)"', match.group(0))
    for key, val in attrs:
        fixed_tag += f' {key}="{val}"'
    # Add srcset if it exists
    if srcset_match:
        fixed_tag += f' srcset="{new_srcset_str}"'

    fixed_tag += '>'
    return fixed_tag


# Apply regex to all <img> tags
html_fixed = re.sub(r'<img[^>]+>', fix_img_tag, html)

# Write to output
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_fixed)
