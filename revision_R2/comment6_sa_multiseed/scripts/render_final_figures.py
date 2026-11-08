from common import *
import fitz,xml.etree.ElementTree as ET
records=[]
for name in ['Figure_R2C6_SA_seed_stability','Figure_R2C6_budget_and_regret']:
 p=OUT/f'figures/{name}.pdf';d=fitz.open(str(p));assert len(d)==1
 dest=OUT/f'audit/{name}_actualPDF.png';d[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(str(dest))
 svg=ET.parse(OUT/f'figures/{name}.svg');texts=svg.findall('.//{http://www.w3.org/2000/svg}text')
 records.append(dict(name=name,pages=len(d),pdf_sha256=sha(p),png_sha256=sha(OUT/f'figures/{name}.png'),svg_sha256=sha(OUT/f'figures/{name}.svg'),editable_svg_text_elements=len(texts),actual_PDF_render=str(dest),render_sha256=sha(dest)))
dump(OUT/'audit/figure_PDF_render_record.json',records)
print('Rendered final PDFs',records)
