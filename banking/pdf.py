import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


def build_receipt_pdf(
    *,
    subtitle: str,
    receipt_code: str,
    timestamp,
    rows: list[tuple[str, str]],
    amount_label: str,
    amount_value: str,
    footer_note: str,
) -> bytes:
    """Render a styled NK-Bank PDF receipt and return raw PDF bytes."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    navy = colors.HexColor('#0f2942')
    teal = colors.HexColor('#0d9488')
    slate = colors.HexColor('#475569')
    border = colors.HexColor('#cbd5e1')
    row_alt = colors.HexColor('#f8fafc')
    mint_bg = colors.HexColor('#ecfdf5')
    mint_fg = colors.HexColor('#065f46')

    pdf.setTitle(f'NK-Bank {subtitle} - {receipt_code}')

    # Header banner
    banner_height = 96
    pdf.setFillColor(navy)
    pdf.rect(0, height - banner_height, width, banner_height, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawString(54, height - 46, 'NK-BANK')
    pdf.setFont('Helvetica', 12)
    pdf.drawString(54, height - 68, subtitle)

    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawRightString(width - 54, height - 46, receipt_code)
    pdf.setFillColor(teal)
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawRightString(width - 54, height - 66, 'STATUS: COMPLETED')

    # Timestamp metadata
    local_ts = timezone.localtime(timestamp)
    pdf.setFillColor(slate)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(54, height - 124, f'Issued: {local_ts.strftime("%Y-%m-%d %H:%M:%S %Z")}')

    # Summary table
    table_x = 54
    table_width = width - 108
    label_width = 155
    value_x = table_x + label_width + 12
    value_max_width = table_width - label_width - 24
    y = height - 150

    for idx, (label, raw_value) in enumerate(rows):
        wrapped_lines = simpleSplit(str(raw_value), 'Helvetica', 10, value_max_width) or ['—']
        row_height = max(28, 12 + len(wrapped_lines) * 14)

        if idx % 2 == 0:
            pdf.setFillColor(row_alt)
            pdf.rect(table_x, y - row_height, table_width, row_height, stroke=0, fill=1)

        pdf.setStrokeColor(border)
        pdf.setLineWidth(0.6)
        pdf.rect(table_x, y - row_height, table_width, row_height, stroke=1, fill=0)

        pdf.setFillColor(slate)
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(table_x + 12, y - 18, label)

        pdf.setFillColor(colors.black)
        pdf.setFont('Helvetica', 10)
        line_y = y - 18
        for line in wrapped_lines:
            pdf.drawString(value_x, line_y, line)
            line_y -= 14

        y -= row_height

    # Highlighted amount bar
    amount_height = 38
    y -= 14
    pdf.setFillColor(mint_bg)
    pdf.setStrokeColor(teal)
    pdf.setLineWidth(1)
    pdf.rect(table_x, y - amount_height, table_width, amount_height, stroke=1, fill=1)

    pdf.setFillColor(mint_fg)
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(table_x + 12, y - 24, amount_label)
    pdf.drawRightString(table_x + table_width - 12, y - 24, amount_value)

    # Footer
    pdf.setStrokeColor(border)
    pdf.setLineWidth(0.5)
    pdf.line(54, 72, width - 54, 72)
    pdf.setFillColor(slate)
    pdf.setFont('Helvetica', 9)
    pdf.drawString(54, 54, footer_note)
    pdf.drawRightString(width - 54, 54, 'NK-Bank Digital Services')

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def generate_transaction_receipt_pdf(tx) -> bytes:
    """Build PDF receipt bytes for a peer-to-peer Transaction."""
    sender_name = tx.sender.user.get_full_name() or tx.sender.user.username
    receiver_name = tx.receiver.user.get_full_name() or tx.receiver.user.username
    rows = [
        ('Transaction Ref', f'TX-{tx.pk:06d}'),
        ('Sender Name', sender_name),
        ('Sender Account', tx.sender.account_number),
        ('Recipient Name', receiver_name),
        ('Recipient Account', tx.receiver.account_number),
        ('Transfer Note', tx.note or '—'),
    ]
    return build_receipt_pdf(
        subtitle='Official Transaction Receipt',
        receipt_code=f'RECEIPT #TX-{tx.pk:06d}',
        timestamp=tx.timestamp,
        rows=rows,
        amount_label='Transfer Amount',
        amount_value=f'${tx.amount:,.2f}',
        footer_note='This electronic receipt confirms a completed NK-Bank peer-to-peer transfer.',
    )


def generate_donation_receipt_pdf(donation) -> bytes:
    """Build PDF receipt bytes for a charitable Donation."""
    donor_name = donation.donor.user.get_full_name() or donation.donor.user.username
    rows = [
        ('Donation Ref', f'DON-{donation.pk:06d}'),
        ('Donor Name', donor_name),
        ('Donor Account', donation.donor.account_number),
        ('Charity Name', donation.charity_name),
        ('Message', donation.message or '—'),
    ]
    return build_receipt_pdf(
        subtitle='Official Donation Receipt',
        receipt_code=f'RECEIPT #DON-{donation.pk:06d}',
        timestamp=donation.timestamp,
        rows=rows,
        amount_label='Donation Amount',
        amount_value=f'${donation.amount:,.2f}',
        footer_note='Thank you for your generous charitable contribution via NK-Bank.',
    )
