import html
from pathlib import Path
from typing import Dict, List

import jinja2
from fpdf import FPDF, html as libhtml, Template


class PDFReport(FPDF):

    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        self.set_compression(False)
        self.base_dir = Path(__file__).resolve().parent
        self.add_font(
            family='DejaVuSansCondensed',
            fname=str(self.base_dir.joinpath('ttf', 'DejaVuSansCondensed.ttf')),
            uni=True
        )

    def from_jinja_template(
        self, name: str, data: Dict = None
    ) -> bytes:
        path = self.base_dir.joinpath('jinja', name)
        if not path.exists():
            raise RuntimeError(f'Not found jinja template "{name}"')
        with open(path, 'r') as f:
            j2 = f.read()
        tmp = jinja2.Template(source=j2)
        kwargs = {}
        if data:
            kwargs = data
        txt = tmp.render(**kwargs)
        return self.from_html(txt)

    def from_html(
        self, text: str, font_family: str = 'DejaVuSansCondensed'
    ) -> bytes:
        self.add_page()
        h2p = libhtml.HTML2FPDF(self)
        text = html.unescape(text)
        if font_family:
            self.set_font(font_family)
        h2p.feed(text)
        self.close()
        return self.buffer.encode("latin1")

    def from_template(
        self, elements: List,
        mapping: Dict = None,
        font_family: str = 'DejaVuSansCondensed'
    ):
        self.add_page()
        tmp = Template(format="A4", elements=elements)
        tmp.add_page()
        if font_family:
            self.set_font(font_family)
        if mapping:
            for key, value in mapping.items():
                tmp[key] = value
        buffer: str = tmp.render('report2.pdf', dest='S')
        return buffer.encode("latin1")
