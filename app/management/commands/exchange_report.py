import os.path
import asyncio

from django.core.management.base import BaseCommand
from fpdf import FPDF

from reports import PDFReport


html = """
<H1 align="center">html2fpdf</H1>
<h2>Basic usage</h2>
<p>You can now easily print text mixing different
styles : <B>bold</B>, <I>italic</I>, <U>underlined</U>, or
<B><I><U>all at once</U></I></B>!<BR>You can also insert links
on text, such as <A HREF="http://www.fpdf.org">www.fpdf.org</A>,
or on an image: click on the logo.<br>
<center>
<A HREF="http://www.fpdf.org"><img src="https://ja-africa.org/wp-content/uploads/2020/02/FedEx-Logo-PNG-Transparent-300x96.png" width="104" height="71"></A>
</center>
<h3>Sample List ПРивет</h3>
<ul><li>option 1</li>
<ol><li>option 2</li></ol>
<li>option 3</li></ul>

<table border="0" align="center" width="50%">
<thead><tr><th width="30%">Header 1</th><th width="70%">header 2</th></tr></thead>
<tbody>
<tr><td>cell 1</td><td>cell 2</td></tr>
<tr><td>cell 2</td><td>cell 3</td></tr>
</tbody>
</table>
"""

elements = [
    { 'name': 'company_logo', 'type': 'I', 'x1': 20.0, 'y1': 17.0, 'x2': 78.0, 'y2': 30.0, 'font': None, 'size': 0.0, 'bold': 0, 'italic': 0, 'underline': 0, 'foreground': 0, 'background': 0, 'align': 'I', 'text': 'logo', 'priority': 2, },
    { 'name': 'company_name', 'type': 'T', 'x1': 17.0, 'y1': 32.5, 'x2': 115.0, 'y2': 37.5, 'font': 'Arial', 'size': 12.0, 'bold': 1, 'italic': 0, 'underline': 0, 'foreground': 0, 'background': 0, 'align': 'I', 'text': '', 'priority': 2, },
    { 'name': 'box', 'type': 'B', 'x1': 15.0, 'y1': 15.0, 'x2': 185.0, 'y2': 260.0, 'font': 'Arial', 'size': 0.0, 'bold': 0, 'italic': 0, 'underline': 0, 'foreground': 0, 'background': 0, 'align': 'I', 'text': None, 'priority': 0, },
    { 'name': 'box_x', 'type': 'B', 'x1': 95.0, 'y1': 15.0, 'x2': 105.0, 'y2': 25.0, 'font': 'Arial', 'size': 0.0, 'bold': 1, 'italic': 0, 'underline': 0, 'foreground': 0, 'background': 0, 'align': 'I', 'text': None, 'priority': 2, },
    { 'name': 'line1', 'type': 'L', 'x1': 100.0, 'y1': 25.0, 'x2': 100.0, 'y2': 57.0, 'font': 'Arial', 'size': 0, 'bold': 0, 'italic': 0, 'underline': 0, 'foreground': 0, 'background': 0, 'align': 'I', 'text': None, 'priority': 3, },
    { 'name': 'barcode', 'type': 'BC', 'x1': 20.0, 'y1': 246.5, 'x2': 140.0, 'y2': 254.0, 'font': 'Interleaved 2of5 NT', 'size': 0.75, 'bold': 0, 'italic': 0, 'underline': 0, 'foreground': 0, 'background': 0, 'align': 'I', 'text': '200000000001000159053338016581200810081', 'priority': 3, },
]


class Command(BaseCommand):

    """PDF Report"""

    DEF_TIMEOUT = 60

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            help="Output file path"
        )

    def handle(self, *args, **options):
        path = options['path']
        report = PDFReport()
        # buffer = report.from_template(
        #     elements,
        #     mapping={
        #         'company_name': 'RuSwift',
        #         'company_logo': 'https://ja-africa.org/wp-content/uploads/2020/02/FedEx-Logo-PNG-Transparent-300x96.png'
        #     }
        # )
        buffer = report.from_jinja_template(name='deposit.mass-payments.j2')
        # buffer = report.from_html(html)
        with open(path, 'w+b') as f:
            f.write(buffer)

    def test(self):
        pdf = FPDF()
        pdf.add_page()
        #pdf.set_text_shaping(True)

        # Add a DejaVu Unicode font (uses UTF-8)
        # Supports more than 200 languages. For a coverage status see:
        # http://dejavu.svn.sourceforge.net/viewvc/dejavu/trunk/dejavu-fonts/langcover.txt
        pdf.add_font(family='DejaVuSansCondensed', fname='/app/exchange/reports/ttf/DejaVuSansCondensed.ttf', uni=True)
        pdf.set_font('DejaVuSansCondensed', size=14)

        text = u"""
        English: Hello World
        Greek: Γειά σου κόσμος
        Polish: Witaj świecie
        Portuguese: Olá mundo
        Russian: Здравствуй, Мир
        Vietnamese: Xin chào thế giới
        Arabic: مرحبا العالم
        Hebrew: שלום עולם
        """

        for txt in text.split('\n'):
            pdf.write(8, txt)
            pdf.ln(8)

        # Add a Indic Unicode font (uses UTF-8)
        # Supports: Bengali, Devanagari, Gujarati,
        #           Gurmukhi (including the variants for Punjabi)
        #           Kannada, Malayalam, Oriya, Tamil, Telugu, Tibetan
        # pdf.add_font(fname='gargi.ttf')
        # pdf.set_font('gargi', size=14)
        pdf.write(8, u'Hindi: नमस्ते दुनिया')
        pdf.ln(20)

        # Add a AR PL New Sung Unicode font (uses UTF-8)
        # The Open Source Chinese Font (also supports other east Asian languages)
        # pdf.add_font(fname='fireflysung.ttf')
        # pdf.set_font('fireflysung', size=14)
        pdf.write(8, u'Chinese: 你好世界\n')
        pdf.write(8, u'Japanese: こんにちは世界\n')
        pdf.ln(10)

        # Add a Alee Unicode font (uses UTF-8)
        # General purpose Hangul truetype fonts that contain Korean syllable
        # and Latin9 (iso8859-15) characters.
        # pdf.add_font(fname='Eunjin.ttf')
        # pdf.set_font('Eunjin', size=14)
        pdf.write(8, u'Korean: 안녕하세요')
        pdf.ln(20)

        # Add a Fonts-TLWG (formerly ThaiFonts-Scalable) (uses UTF-8)
        # pdf.add_font(fname='Waree.ttf')
        # pdf.set_font('Waree', size=14)
        pdf.write(8, u'Thai: สวัสดีชาวโลก')
        pdf.ln(20)

        # Select a standard font (uses windows-1252)
        pdf.set_font('helvetica', size=14)
        pdf.ln(10)
        pdf.write(5, 'This is standard built-in font')

        pdf.output("unicode.pdf")
