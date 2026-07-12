import fitz, json

with open('config.json') as f:
    cfg = json.load(f)

from boxsdk import OAuth2, Client
box  = cfg['box']
auth = OAuth2(client_id=box['client_id'], client_secret=box['client_secret'], access_token=box['access_token'])
client = Client(auth)

pdf_bytes = client.file('2338248099851').content()
doc = fitz.open(stream=pdf_bytes, filetype='pdf')
doc.authenticate(cfg['pdf_password'])

for i in range(len(doc)):
    print(f"=== PAGE {i+1} ===")
    page = doc.load_page(i)
    blocks = page.get_text('dict')['blocks']
    for b in blocks:
        if b.get('type') == 0:
            for line in b['lines']:
                for span in line['spans']:
                    color = span.get('color', 0)
                    text  = span.get('text', '').strip()
                    if text:
                        r  = (color >> 16) & 0xFF
                        g  = (color >> 8)  & 0xFF
                        bv = color & 0xFF
                        print(f"  RGB=({r:3},{g:3},{bv:3})  FONT={span['font']:<40}  SIZE={span['size']:4.1f}  TEXT={repr(text)}")
    print()
