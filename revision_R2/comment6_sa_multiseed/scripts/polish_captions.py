"""Typography only; does not redraw or alter figure data."""
from common import *
replacements={'All100':'All 100','with1.5IQR':'with 1.5 IQR','replicate0':'replicate 0','not100':'not 100','frozen1e-9 relative objective rule':'frozen rule |J−J*|≤1e-9 max(1,|J*|)','.27 runs':'. 27 runs','below256':'below 256','after1000':'after 1000','with10 technical':'with 10 technical'}
frozen={r['path'] for r in js(OUT/'run_manifest.json')['frozen_scripts']}
for p in [OUT/'figures/Figure_captions_EN.md',OUT/'scripts/plot_figures.py']:
 assert str(p) not in frozen
 text=p.read_text(encoding='utf-8')
 for before,after in replacements.items():text=text.replace(before,after)
 p.write_text(text,encoding='utf-8')
print('Caption typography corrected; no plots or numerical data changed')
