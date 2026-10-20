"""Reuse the repeated gzip/Base64 embedding step with file-path arguments."""
from pathlib import Path
import argparse,base64,gzip,re

def embed_model(template,glb,output):
 text=Path(template).read_text(encoding='utf-8')
 if re.search(r'(?m)^(?:<{7}(?: .*)?|={7}|>{7}(?: .*)?)\r?$',text):
  raise ValueError('Template contains unresolved Git merge conflict markers')
 if sum(1 for _ in re.finditer(r"const GLB_GZIP_B64='[^']*';",text))!=1:
  raise ValueError('Template must contain exactly one embedded model declaration')
 raw=Path(glb).read_bytes();compressed=gzip.compress(raw,compresslevel=9,mtime=0)
 assert gzip.decompress(compressed)==raw
 text,n=re.subn(r"const GLB_GZIP_B64='[^']*';",lambda _:"const GLB_GZIP_B64='"+base64.b64encode(compressed).decode()+"';",text,count=1)
 if n!=1:raise ValueError('Template model placeholder missing')
 target=Path(output)
 if target.resolve()in[Path(template).resolve(),Path(glb).resolve()]or target.exists():raise ValueError('Choose a new output file')
 target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('glb');p.add_argument('output');a=p.parse_args()
 embed_model(Path(__file__).with_name('campus.template.html'),a.glb,a.output)
