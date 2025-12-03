import re


input_file = "index.html"


output_file = "templates/index.html"


with open(input_file, 'r', encoding='utf-8') as f:
    html = f.read()



def fix_img_tag(match):
    tag = match.group(0)


    src_match = re.search(r'src="([^"]+)"', tag)
    if not src_match:
        return tag
    filename = src_match.group(1).split('/')[-1].split('?')[0]


    new_src = f'{{{{ url_for(\'static\', filename=\'images/{filename}\') }}}}'


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


    tag = re.sub(r'src="[^"]+"', f'src="{new_src}"', tag, count=1)


    tag = re.sub(r'(src|alt)="[^"]+"', '', tag[1:-1])

    alt_match = re.search(r'alt="([^"]*)"', match.group(0))
    alt_text = alt_match.group(1) if alt_match else filename
    fixed_tag = f'<img src="{new_src}" alt="{alt_text}"'


    attrs = re.findall(r'(width|height|style|sizes|loading|decoding|class|id|data-[^=]+)="([^"]+)"', match.group(0))
    for key, val in attrs:
        fixed_tag += f' {key}="{val}"'

    if srcset_match:
        fixed_tag += f' srcset="{new_srcset_str}"'

    fixed_tag += '>'
    return fixed_tag



html_fixed = re.sub(r'<img[^>]+>', fix_img_tag, html)


with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_fixed)
