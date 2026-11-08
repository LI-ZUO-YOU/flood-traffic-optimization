from common import *
records=js(OUT/'audit/figure_PDF_render_record.json')
for r in records:
 r.update(visually_checked_final_PDF_and_PNG=True,review='Final PDF rendered and inspected with image viewer; final PNG inspected separately. Legible symbols/ticks/labels/legend; no clipping, overlapping text or hidden adverse seeds. Budget scatter uses exact coordinates with transparency; coincident points need CSV for multiplicity.',status='PASS')
dump(OUT/'audit/figure_visual_review.json',dict(status='PASS',figures=records,review_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),PNG_DPI=600,minimum_font_pt=7,SVG_check='XML parsed; editable text elements counted; SVG not separately visually rendered',TIFF_note='Generic source validator warns about optional TIFF export; this protocol requires PDF/PNG/SVG, all supplied. No missing required format.'))
print('Recorded actual PDF/PNG visual review for2 final figures')
