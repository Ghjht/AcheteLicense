import os
from datetime import datetime
from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate


def generate_invoice(order):
    invoice_dir = current_app.config['INVOICE_FOLDER']
    os.makedirs(invoice_dir, exist_ok=True)

    filename = f'invoice_{order.id}.pdf'
    filepath = os.path.join(invoice_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=26,
        textColor=HexColor('#6c5ce7'),
        spaceAfter=4*mm,
        alignment=TA_LEFT
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#a1a1aa'),
        spaceAfter=10*mm
    )

    header_style = ParagraphStyle(
        'HeaderRight',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#71717a'),
        alignment=TA_RIGHT
    )

    info_label_style = ParagraphStyle(
        'InfoLabel',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#71717a'),
        spaceAfter=1*mm
    )

    info_value_style = ParagraphStyle(
        'InfoValue',
        parent=styles['Normal'],
        fontSize=11,
        textColor=HexColor('#1a1a2e'),
        spaceAfter=4*mm
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#ffffff'),
        alignment=TA_CENTER,
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#1a1a2e'),
        alignment=TA_CENTER,
    )

    table_cell_left = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#1a1a2e'),
        alignment=TA_LEFT,
    )

    total_style = ParagraphStyle(
        'TotalStyle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=HexColor('#1a1a2e'),
        alignment=TA_RIGHT,
    )

    elements = []

    elements.append(Paragraph('ACHETELICENSE', title_style))
    elements.append(Paragraph('Premium Digital License Marketplace', subtitle_style))

    invoice_date = order.paid_at or order.created_at

    data_right = [
        [Paragraph('Invoice #', header_style), Paragraph(f'INV-{order.id:04d}', header_style)],
        [Paragraph('Date:', header_style), Paragraph(invoice_date.strftime('%B %d, %Y'), header_style)],
        [Paragraph('Status:', header_style), Paragraph('Paid', header_style)],
    ]
    right_table = Table(data_right, colWidths=[30*mm, 50*mm])
    right_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
    ]))

    left_data = [
        [Paragraph('Bill To:', info_label_style)],
        [Paragraph(order.customer_name or order.customer_email or 'Customer', info_value_style)],
        [Paragraph(order.customer_email or '', info_label_style)],
    ]
    left_table = Table(left_data, colWidths=[80*mm])

    info_table = Table(
        [[left_table, right_table]],
        colWidths=[90*mm, 80*mm]
    )
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))

    table_data = [
        [
            Paragraph('Product', table_header_style),
            Paragraph('License', table_header_style),
            Paragraph('Qty', table_header_style),
            Paragraph('Price', table_header_style),
            Paragraph('Total', table_header_style),
        ]
    ]

    for item in order.items:
        table_data.append([
            Paragraph(item.product_name, table_cell_left),
            Paragraph(item.license_key or '-', table_cell_style),
            Paragraph(str(item.quantity), table_cell_style),
            Paragraph(f'DH {item.price:.2f}', table_cell_style),
            Paragraph(f'DH {(item.price * item.quantity):.2f}', table_cell_style),
        ])

    total_row = [
        Paragraph('', table_cell_left),
        Paragraph('', table_cell_style),
        Paragraph('', table_cell_style),
        Paragraph('<b>TOTAL</b>', ParagraphStyle('TotalLabel', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT, textColor=HexColor('#1a1a2e'))),
        Paragraph(f'<b>${order.total_amount:.2f}</b>', ParagraphStyle('TotalValue', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER, textColor=HexColor('#6c5ce7'))),
    ]
    table_data.append(total_row)

    col_widths = [60*mm, 35*mm, 15*mm, 25*mm, 25*mm]
    invoice_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#6c5ce7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.5, HexColor('#e4e4e7')),
        ('LINEBELOW', (0, -1), (-1, -1), 1, HexColor('#6c5ce7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [HexColor('#ffffff'), HexColor('#f8f8ff')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6*mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6*mm),
    ]))

    elements.append(invoice_table)
    elements.append(Spacer(1, 15*mm))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#a1a1aa'),
        alignment=TA_CENTER
    )

    elements.append(Paragraph('Thank you for your purchase!', total_style))
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(
        'This invoice was generated automatically by AcheteLicense. '
        'All digital products are delivered via email and your account dashboard.',
        footer_style
    ))

    doc.build(elements)
    return filepath
