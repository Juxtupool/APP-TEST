import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_bom_pdf():
    desktop_path = r"C:\Users\pulak\Desktop\Macropad_BOM_India.pdf"
    
    doc = SimpleDocTemplate(
        desktop_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1A202C')
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#4A5568')
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=10,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#2D3748')
    )
    
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1A202C')
    )
    
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1A202C')
    )
    
    cell_header = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )
    
    link_style = ParagraphStyle(
        'CellLink',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#2B6CB0')
    )
    
    elements = []
    
    # Title Section
    elements.append(Paragraph("OVERCONTROL / MONOLITH MACROPAD", title_style))
    elements.append(Paragraph("Bill of Materials (BOM) & Sourcing Guide — India Market (INR)", subtitle_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2B6CB0'), spaceBefore=2, spaceAfter=10))
    
    # Section 1: RP2040-Zero Version BOM
    elements.append(Paragraph("Option A: RP2040-Zero Version (Recommended / Easy Assembly)", h2_style))
    elements.append(Paragraph("Uses an all-in-one RP2040-Zero module containing the Dual-Core MCU, USB-C port, 3.3V LDO, Crystal, Flash memory, and RGB LED.", body_style))
    elements.append(Spacer(1, 6))
    
    rp_data = [
        [
            Paragraph("Item", cell_header),
            Paragraph("Component", cell_header),
            Paragraph("Description / Package", cell_header),
            Paragraph("Qty", cell_header),
            Paragraph("Unit (₹)", cell_header),
            Paragraph("Total (₹)", cell_header),
            Paragraph("Recommended Stores", cell_header)
        ],
        [
            Paragraph("1", cell_style),
            Paragraph("<b>RP2040-Zero</b>", cell_style),
            Paragraph("Waveshare / Generic RP2040 Module with USB-C", cell_style),
            Paragraph("1", cell_style),
            Paragraph("₹310", cell_style),
            Paragraph("₹310", cell_bold),
            Paragraph("<font color='#2B6CB0'>Robu.in / QuartzComponents / Zbotic</font>", link_style)
        ],
        [
            Paragraph("2", cell_style),
            Paragraph("<b>EC11 Encoder</b>", cell_style),
            Paragraph("Rotary Encoder with Push Switch (20mm D-Shaft)", cell_style),
            Paragraph("1", cell_style),
            Paragraph("₹45", cell_style),
            Paragraph("₹45", cell_bold),
            Paragraph("<font color='#2B6CB0'>Robu.in / Flyrobo / QuartzComponents</font>", link_style)
        ],
        [
            Paragraph("3", cell_style),
            Paragraph("<b>Mech Switches</b>", cell_style),
            Paragraph("Outemu / Gateron 3-Pin / 5-Pin Keyswitches", cell_style),
            Paragraph("6", cell_style),
            Paragraph("₹22", cell_style),
            Paragraph("₹132", cell_bold),
            Paragraph("<font color='#2B6CB0'>Meckeys / StacksKB / NeoMacro</font>", link_style)
        ],
        [
            Paragraph("4", cell_style),
            Paragraph("<b>Hardware</b>", cell_style),
            Paragraph("M2 × 6mm/8mm Brass Standoffs + Screws", cell_style),
            Paragraph("4", cell_style),
            Paragraph("₹8", cell_style),
            Paragraph("₹32", cell_bold),
            Paragraph("<font color='#2B6CB0'>Robu.in / Amazon India</font>", link_style)
        ],
        [
            Paragraph("<b>TOTAL</b>", cell_bold),
            Paragraph("<b>RP2040 Hardware Components Total</b>", cell_bold),
            Paragraph("-", cell_style),
            Paragraph("<b>12</b>", cell_bold),
            Paragraph("-", cell_style),
            Paragraph("<b>₹519</b>", cell_bold),
            Paragraph("<b>+ PCB (~₹75/ea from JLCPCB)</b>", cell_bold)
        ]
    ]
    
    t_rp = Table(rp_data, colWidths=[28, 80, 160, 30, 45, 55, 142])
    t_rp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#F7FAFC')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EDF2F7')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_rp)
    elements.append(Spacer(1, 14))
    
    # Section 2: CH32V203 Discrete Version BOM
    elements.append(Paragraph("Option B: CH32V203 RISC-V Version (Discrete On-Board Chip)", h2_style))
    elements.append(Paragraph("Uses bare microcontroller IC and discrete SMD passives on the PCB. Ultra low component cost.", body_style))
    elements.append(Spacer(1, 6))
    
    ch_data = [
        [
            Paragraph("Item", cell_header),
            Paragraph("Designator", cell_header),
            Paragraph("Component / Package", cell_header),
            Paragraph("Qty", cell_header),
            Paragraph("Unit (₹)", cell_header),
            Paragraph("Total (₹)", cell_header),
            Paragraph("Recommended Stores", cell_header)
        ],
        [
            Paragraph("1", cell_style),
            Paragraph("U2", cell_style),
            Paragraph("CH32V203C8T6 (32-bit RISC-V, LQFP-48)", cell_style),
            Paragraph("1", cell_style),
            Paragraph("₹69", cell_style),
            Paragraph("₹69", cell_bold),
            Paragraph("<font color='#2B6CB0'>ETStore / Punoscho / Robu</font>", link_style)
        ],
        [
            Paragraph("2", cell_style),
            Paragraph("U1", cell_style),
            Paragraph("ME6211C33M5G (3.3V 500mA LDO, SOT-23-5)", cell_style),
            Paragraph("1", cell_style),
            Paragraph("₹12", cell_style),
            Paragraph("₹12", cell_bold),
            Paragraph("<font color='#2B6CB0'>Robu.in / Probots / Evelta</font>", link_style)
        ],
        [
            Paragraph("3", cell_style),
            Paragraph("J1", cell_style),
            Paragraph("USB-C 16-Pin Receptacle (TYPE-C-31-M-12)", cell_style),
            Paragraph("1", cell_style),
            Paragraph("₹18", cell_style),
            Paragraph("₹18", cell_bold),
            Paragraph("<font color='#2B6CB0'>QuartzComponents / Robu</font>", link_style)
        ],
        [
            Paragraph("4", cell_style),
            Paragraph("SW1", cell_style),
            Paragraph("EC11 Rotary Encoder with Push Button", cell_style),
            Paragraph("1", cell_style),
            Paragraph("₹45", cell_style),
            Paragraph("₹45", cell_bold),
            Paragraph("<font color='#2B6CB0'>Robu.in / Flyrobo</font>", link_style)
        ],
        [
            Paragraph("5", cell_style),
            Paragraph("S1-S6", cell_style),
            Paragraph("Mechanical Keyboard Switches (6 pcs)", cell_style),
            Paragraph("6", cell_style),
            Paragraph("₹22", cell_style),
            Paragraph("₹132", cell_bold),
            Paragraph("<font color='#2B6CB0'>Meckeys / StacksKB</font>", link_style)
        ],
        [
            Paragraph("6", cell_style),
            Paragraph("R1, R2", cell_style),
            Paragraph("5.1kΩ 0603 SMD Resistors (USB CC)", cell_style),
            Paragraph("2", cell_style),
            Paragraph("₹1.50", cell_style),
            Paragraph("₹3", cell_bold),
            Paragraph("<font color='#2B6CB0'>QuartzComponents / Robu</font>", link_style)
        ],
        [
            Paragraph("7", cell_style),
            Paragraph("R3, R4", cell_style),
            Paragraph("10kΩ 0603 SMD Resistors (BOOT0/RST)", cell_style),
            Paragraph("2", cell_style),
            Paragraph("₹1.50", cell_style),
            Paragraph("₹3", cell_bold),
            Paragraph("<font color='#2B6CB0'>QuartzComponents / Robu</font>", link_style)
        ],
        [
            Paragraph("8", cell_style),
            Paragraph("C1, C2", cell_style),
            Paragraph("10µF 0603 16V Ceramic Capacitors", cell_style),
            Paragraph("2", cell_style),
            Paragraph("₹3.50", cell_style),
            Paragraph("₹7", cell_bold),
            Paragraph("<font color='#2B6CB0'>QuartzComponents / Robu</font>", link_style)
        ],
        [
            Paragraph("9", cell_style),
            Paragraph("C3-C6", cell_style),
            Paragraph("0.1µF (100nF) 0603 50V MLCC Caps", cell_style),
            Paragraph("4", cell_style),
            Paragraph("₹1.50", cell_style),
            Paragraph("₹6", cell_bold),
            Paragraph("<font color='#2B6CB0'>QuartzComponents / Robu</font>", link_style)
        ],
        [
            Paragraph("10", cell_style),
            Paragraph("H1-H4", cell_style),
            Paragraph("M2 × 6mm/8mm Brass Standoffs + Screws", cell_style),
            Paragraph("4", cell_style),
            Paragraph("₹8", cell_style),
            Paragraph("₹32", cell_bold),
            Paragraph("<font color='#2B6CB0'>Robu.in / Amazon India</font>", link_style)
        ],
        [
            Paragraph("<b>TOTAL</b>", cell_bold),
            Paragraph("<b>-</b>", cell_style),
            Paragraph("<b>CH32V203 Hardware Components Total</b>", cell_bold),
            Paragraph("<b>23</b>", cell_bold),
            Paragraph("-", cell_style),
            Paragraph("<b>₹327</b>", cell_bold),
            Paragraph("<b>+ PCB (~₹75/ea from JLCPCB)</b>", cell_bold)
        ]
    ]
    
    t_ch = Table(ch_data, colWidths=[28, 50, 190, 30, 45, 55, 142])
    t_ch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2D3748')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#F7FAFC')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EDF2F7')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_ch)
    elements.append(Spacer(1, 14))
    
    # Section 3: Comparison & Verdict
    elements.append(Paragraph("Comparison & Recommendation Summary", h2_style))
    
    comp_data = [
        [
            Paragraph("Feature", cell_header),
            Paragraph("Option A: RP2040-Zero", cell_header),
            Paragraph("Option B: CH32V203 Discrete", cell_header)
        ],
        [
            Paragraph("<b>Assembly Difficulty</b>", cell_style),
            Paragraph("Very Easy (4 solder parts only, no tiny SMD)", cell_style),
            Paragraph("Moderate (LQFP-48 & 0603 soldering required)", cell_style)
        ],
        [
            Paragraph("<b>Firmware Flashing</b>", cell_style),
            Paragraph("Drag-and-drop .UF2 drive over USB", cell_style),
            Paragraph("WCHISPTool USB or WCH-Link programmer", cell_style)
        ],
        [
            Paragraph("<b>Firmware Support</b>", cell_style),
            Paragraph("QMK, Vial, KMK, CircuitPython, Arduino", cell_style),
            Paragraph("Custom C/C++ (WCH SDK) or QMK fork", cell_style)
        ],
        [
            Paragraph("<b>Total Cost / Board</b>", cell_style),
            Paragraph("<b>₹594 INR</b> (incl. PCB)", cell_bold),
            Paragraph("<b>₹402 INR</b> (incl. PCB)", cell_bold)
        ]
    ]
    
    t_comp = Table(comp_data, colWidths=[120, 210, 210])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#319795')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F7FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_comp)
    
    doc.build(elements)
    print(f"PDF generated successfully at {desktop_path}")

if __name__ == "__main__":
    generate_bom_pdf()
