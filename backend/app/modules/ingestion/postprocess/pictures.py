"""The box of every Docling picture, page by page, in the order Docling writes its "<!-- image -->" markers (22/11).

Runs where Docling runs (docling_worker.py on the laptop, the Kaggle GPU worker, which carries this package): the worker adds "pictures" to each page it
returns, and ingestion/figures.py decides which pictures the vision model reads. Boxes are PDF points with a top-left origin, like PyMuPDF.
Checked: the markers of export_to_markdown(page_no=n) and the pictures of iterate_items(page_no=n) match on 130 of 130 pages (SEC eval_84, 40 documents).
"""
from typing import Dict, List


def page_pictures(document) -> Dict[int, List[List[float]]]:
    from docling_core.types.doc import PictureItem

    out: Dict[int, List[List[float]]] = {}
    for page_no, page in document.pages.items():
        for item, _ in document.iterate_items(page_no=page_no):
            if not isinstance(item, PictureItem):
                continue
            prov = next((p for p in item.prov if p.page_no == page_no), None)
            if prov is None:
                continue
            box = prov.bbox.to_top_left_origin(page_height=page.size.height)
            out.setdefault(page_no, []).append([round(box.l, 1), round(box.t, 1), round(box.r, 1), round(box.b, 1)])
    return out
