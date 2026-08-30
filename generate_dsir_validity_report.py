import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#555555"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 805, "DSIR PRISM Innovation Assessment Report | Project: Overcontrol")
            self.drawRightString(555, 805, "CONFIDENTIAL / TECHNICAL DOSSIER")
            self.setStrokeColor(colors.HexColor("#003366"))
            self.setLineWidth(0.75)
            self.line(40, 798, 555, 798)
            
        # Footer
        self.setStrokeColor(colors.HexColor("#D0D7DE"))
        self.setLineWidth(0.5)
        self.line(40, 42, 555, 42)
        
        self.drawString(40, 30, "Department of Scientific and Industrial Research (DSIR) - PRISM Scheme Compliance")
        self.drawRightString(555, 30, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

def build_pdf(filename="DSIR_Product_Validity_and_Novelty_Assessment.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#003366")    # Navy Blue
    c_secondary = colors.HexColor("#800000")  # Maroon
    c_accent = colors.HexColor("#0D5257")     # Dark Teal
    c_dark = colors.HexColor("#1A202C")       # Off-black
    c_light_bg = colors.HexColor("#F8F9FA")   # Card BG
    c_table_alt = colors.HexColor("#F0F4F8")  # Table Alt Row
    c_success_bg = colors.HexColor("#E6F4EA") # Green BG
    c_success_txt = colors.HexColor("#137333")
    c_border = colors.HexColor("#D0D7DE")
    
    # Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=c_primary,
        alignment=1, # Center
        spaceAfter=4
    )
    
    sub_title_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=c_secondary,
        alignment=1, # Center
        spaceAfter=8
    )
    
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#4A5568"),
        alignment=1,
        spaceAfter=10
    )
    
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_accent,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_dark,
        spaceAfter=5
    )
    
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    bullet_style = ParagraphStyle(
        'Bullet',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1B314B")
    )
    
    table_hdr = ParagraphStyle(
        'TableHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )
    
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=c_dark
    )
    
    table_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=table_cell,
        alignment=1
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold'
    )

    story = []
    
    # ------------------ TITLE & HEADER ------------------
    story.append(Paragraph("DEPARTMENT OF SCIENTIFIC AND INDUSTRIAL RESEARCH (DSIR)", ParagraphStyle('TopGov', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=c_primary, alignment=1)))
    story.append(Paragraph("PROMOTING INNOVATIONS IN INDIVIDUALS, START-UPs and MSMEs (PRISM)", ParagraphStyle('TopSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=c_secondary, alignment=1)))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Innovation Novelty & Validity Assessment Report", title_style))
    story.append(Paragraph("Compliance Evaluation under DSIR PRISM Category-II Guidelines & Indian Patent Act", sub_title_style))
    story.append(Paragraph("<b>Project:</b> Overcontrol — Intelligent Context-Aware Hardware Macro Controller | <b>Innovator:</b> Pulak Nayak | <b>Status:</b> Category-II Application", meta_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceBefore=2, spaceAfter=8))
    
    # ------------------ EXECUTIVE VERDICT BOX ------------------
    verdict_content = [
        [Paragraph("<b>OFFICIAL EVALUATION VERDICT: VALID ORIGINAL INNOVATION (NOT COPIED)</b>", ParagraphStyle('VHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=c_success_txt, alignment=1))],
        [Paragraph(
            "Based on the statutory guidelines of the <b>Department of Scientific and Industrial Research (DSIR)</b> under the <b>PRISM Scheme</b> (Category-I / Phase-I Category-II), the proposed product (<b>Overcontrol</b>) qualifies as a <b>Valid, Novel, and Indigenous Technological Innovation</b>. It will <b>NOT</b> be classified as a 'copied', 'routine assembly', or 'infringing clone' of existing market devices (such as Elgato Stream Deck, Loupedeck, or generic DIY macro pads) because it introduces demonstrable, patentable novelty in <b>asynchronous hardware-software co-design, real-time context-aware foreground OS process detection, and dynamic sub-millisecond layer remapping</b>.",
            callout_style
        )]
    ]
    t_verdict = Table(verdict_content, colWidths=[515])
    t_verdict.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_success_bg),
        ('BOX', (0,0), (-1,-1), 1.5, c_success_txt),
        ('PADDING', (0,0), (-1,-1), 7),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,0), (-1,0), 3),
    ]))
    story.append(t_verdict)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 1: DSIR RULES ------------------
    story.append(Paragraph("1. Statutory DSIR Guidelines on Novelty vs. Routine Assembly", h1_style))
    story.append(Paragraph(
        "DSIR Project Assessment and Screening Committees (PASC) and TePP Outreach Cum Cluster Innovation Centres (TOCIC) evaluate proposals under strict technical filters. Understanding these criteria establishes why the Overcontrol project is fundamentally eligible:",
        body_style
    ))
    
    rules_table_data = [
        [Paragraph("DSIR Filter Criteria", table_hdr), Paragraph("Disqualification Threshold (Copied / Ineligible)", table_hdr), Paragraph("Overcontrol Project Qualification (Valid)", table_hdr)],
        [
            Paragraph("<b>Novelty & Inventive Step</b>", table_cell),
            Paragraph("Mere cosmetic modification, direct repackaging, or cosmetic enclosures over standard kits.", table_cell),
            Paragraph("Novel tripartite integration: Bare-metal MCU event scheduler + Win32/Edge WebView2 hook engine + sub-2ms dynamic layer swap.", table_cell)
        ],
        [
            Paragraph("<b>Indigenous R&D & Import Substitution</b>", table_cell),
            Paragraph("Importing foreign finished goods for domestic white-labeling or simple trading.", table_cell),
            Paragraph("100% indigenous circuit schematics (KiCad), embedded C/Rust firmware, and CAD tooling to replace ₹15,000–₹35,000 imported peripherals.", table_cell)
        ],
        [
            Paragraph("<b>Substantive Engineering vs. Routine Assembly</b>", table_cell),
            Paragraph("Soldering off-the-shelf development modules without custom circuit layout or firmware engineering.", table_cell),
            Paragraph("Custom 4-layer PCB layout with 90Ω USB-C differential impedance matching, TVS diode ESD arrays, and quadrature encoder kinematics.", table_cell)
        ],
        [
            Paragraph("<b>Intellectual Property (IPR) Potential</b>", table_cell),
            Paragraph("Known generic methods without technical advancement (barred under Sec 3, Indian Patents Act).", table_cell),
            Paragraph("Indian Patent Specification prepared for 'Context-Aware Reconfigurable Hardware Input Device and Method for Automated Dynamic Application Mapping' (IPC G06F3/02).", table_cell)
        ]
    ]
    t_rules = Table(rules_table_data, colWidths=[115, 195, 205])
    t_rules.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_table_alt])
    ]))
    story.append(t_rules)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 2: SYSTEM ARCHITECTURE & TECHNICAL DIFFERENTIATION ------------------
    story.append(Paragraph("2. Technical Breakdown: Why Overcontrol is NOT a Clone", h1_style))
    story.append(Paragraph(
        "A common point of scrutiny during DSIR screening is distinguishing between a generic DIY microcontroller project and genuine commercial-grade industrial R&D. Overcontrol solves specific technical challenges across three distinct layers:",
        body_style
    ))
    
    story.append(Paragraph("<b>A. Hardware & Physical Layer Innovation</b>", h2_style))
    story.append(Paragraph("• <b>Dual-Architecture MCU Foundation:</b> Custom multi-layer KiCad PCB supporting 32-bit dual-core RP2040 (ARM Cortex-M0+ at 133MHz) and CH32V203 (RISC-V) with native USB hardware controllers.", bullet_style))
    story.append(Paragraph("• <b>Signal Integrity & ESD Hardening:</b> Industrial-grade transient voltage suppression (TVS) diode arrays on USB high-speed lines, custom decoupling networks, and 90-ohm controlled differential impedance routing.", bullet_style))
    story.append(Paragraph("• <b>Kinematics & Dual Quadrature Decoding:</b> Integration of dual high-resolution optical/rotary quadrature encoders with 2-bit Gray code hardware transition tracking for zero missed rotational steps during high-speed scrubbing.", bullet_style))

    story.append(Paragraph("<b>B. Firmware & Protocol Layer Innovation</b>", h2_style))
    story.append(Paragraph("• <b>Sub-Millisecond Bare-Metal Scheduler:</b> Custom non-blocking interrupt matrix scanner eliminating contact bounce jitter without introducing input lag (<1ms total latency).", bullet_style))
    story.append(Paragraph("• <b>Dual-Endpoint USB Pipeline:</b> Simultaneous standard USB HID (Keyboard/Mouse/Consumer Controls) for OS-level universal driver compatibility + high-speed CDC Virtual Serial for real-time bi-directional parameter streaming.", bullet_style))

    story.append(Paragraph("<b>C. Desktop Daemon & Context-Aware Engine</b>", h2_style))
    story.append(Paragraph("• <b>Ultra-Low Overhead OS Hooking:</b> Native Windows WinEvent background hook engine implemented in Python / Microsoft Edge WebView2, consuming <30MB RAM (compared to >400MB in commercial Electron-based tools).", bullet_style))
    story.append(Paragraph("• <b>Zero-Latency Active Window Mapping:</b> Asynchronous detection of foreground window focus (e.g., instant shift between VS Code, Blender, and Premiere Pro) with automated dynamic hardware keymap deployment in under 2 milliseconds.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(PageBreak()) # Page 2

    # ------------------ SECTION 3: COMPETITIVE BENCHMARKING TABLE ------------------
    story.append(Paragraph("3. Deep Competitive Benchmarking & Prior Art Analysis", h1_style))
    story.append(Paragraph(
        "The following matrix illustrates how Overcontrol compares against commercial market leaders and generic DIY projects, proving clear novelty and market superiority:",
        body_style
    ))

    comp_table_data = [
        [
            Paragraph("Parameter / Feature", table_hdr),
            Paragraph("Elgato Stream Deck<br/>(Commercial Market Leader)", table_hdr),
            Paragraph("Generic DIY Macropad<br/>(Standard Open-Source Kit)", table_hdr),
            Paragraph("Overcontrol V5<br/>(Proposed Innovation)", table_hdr)
        ],
        [
            Paragraph("<b>Target Price in India</b>", table_cell_bold),
            Paragraph("₹15,000 – ₹32,000 (Imported)", table_cell),
            Paragraph("₹2,000 – ₹4,000 (DIY hobby kit)", table_cell),
            Paragraph("<b>₹2,999 – ₹3,499 (Indigenous)</b>", table_cell)
        ],
        [
            Paragraph("<b>Input Mechanisms</b>", table_cell_bold),
            Paragraph("Soft LCD membrane keys only", table_cell),
            Paragraph("Basic mechanical switches only", table_cell),
            Paragraph("<b>Hot-swap mechanical switches + Dual quadrature rotary encoders + OLED</b>", table_cell)
        ],
        [
            Paragraph("<b>OS Context Switching</b>", table_cell_bold),
            Paragraph("Supported via proprietary software", table_cell),
            Paragraph("None (Static manual layer toggle)", table_cell),
            Paragraph("<b>Native Win32 active hook daemon with sub-2ms automated layer injection</b>", table_cell)
        ],
        [
            Paragraph("<b>Software Memory Footprint</b>", table_cell_bold),
            Paragraph("Heavy Electron (~400MB - 600MB RAM)", table_cell),
            Paragraph("No background daemon (or raw QMK)", table_cell),
            Paragraph("<b>Lightweight WebView2 suite (<35MB RAM)</b>", table_cell)
        ],
        [
            Paragraph("<b>Architecture & Customization</b>", table_cell_bold),
            Paragraph("Closed-source proprietary locked ecosystem", table_cell),
            Paragraph("Requires manual firmware re-flashing", table_cell),
            Paragraph("<b>Open API, local & cloud macro registry, hot-reconfigurable</b>", table_cell)
        ],
        [
            Paragraph("<b>DSIR Innovation Status</b>", table_cell_bold),
            Paragraph("Foreign commercial benchmark", table_cell),
            Paragraph("Routine hobby assembly (Ineligible)", table_cell),
            Paragraph("<b>Novel Indigenous Product Innovation (Eligible)</b>", table_cell)
        ]
    ]

    t_comp = Table(comp_table_data, colWidths=[105, 135, 135, 140])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_table_alt])
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 4: COMMITTEE DEFENSE STRATEGY ------------------
    story.append(Paragraph("4. Anticipated DSIR / TOCIC Review Questions & Strategic Defense", h1_style))
    story.append(Paragraph(
        "During the evaluation meeting before the Project Assessment and Screening Committee (PASC), reviewers will rigorously test the boundaries of the innovation. Innovator should use the following structured technical arguments:",
        body_style
    ))

    qa_list = [
        (
            "Q1: 'Macro controllers already exist on the international market (e.g. Stream Deck). Why should DSIR fund this?'",
            "Defense: While auxiliary input devices exist globally, 100% of advanced commercial units are imported into India at prohibitive costs (₹15,000–₹35,000), making them inaccessible for grassroots Indian designers, students, and SMEs. Overcontrol is an indigenously developed, Atmanirbhar hardware-software ecosystem engineered from ground up at <20% of the cost, with distinctive technical advantages including physical hot-swap mechanical switches, dual quadrature precision dials, and open-architecture macro workflows."
        ),
        (
            "Q2: 'You are using standard microcontrollers like RP2040 / CH32V. Does this make the project routine assembly?'",
            "Defense: No. Under DSIR rules and Indian Patent Law, utilizing standard silicon fabrication ICs is the universal standard in embedded R&D. The patentable innovation lies in the custom circuit schematic, 4-layer impedance-matched PCB topology, non-blocking bare-metal interrupt scheduler, and the synchronized dynamic IPC engine that operates between the host operating system and the hardware controller."
        ),
        (
            "Q3: 'How does the software differ from standard keyboard remapping tools like AutoHotkey or VIA?'",
            "Defense: Standard tools like VIA or AutoHotkey operate either purely in software (introducing OS input capture lag) or require manual static profile switching on hardware. Overcontrol implements an integrated tripartite pipeline: an asynchronous OS daemon that intercepts window focus transitions and pushes microcode parameter states via a high-speed CDC serial channel directly into MCU memory in real time without user intervention."
        ),
        (
            "Q4: 'What are the tangible socio-economic benefits under the PRISM mandate?'",
            "Defense: (1) Import Substitution: Eliminates foreign currency outflow for creator peripherals. (2) Assistive Technology: Converts complex multi-key combinations into single tactile switch/rotary motions for motor-impaired individuals. (3) Manufacturing Ecosystem: Generates local electronics prototyping and SMT assembly employment in India."
        )
    ]

    for q, a in qa_list:
        card = [
            [Paragraph(f"<b>{q}</b>", ParagraphStyle('QStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=c_primary))],
            [Paragraph(a, ParagraphStyle('AStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=c_dark))]
        ]
        t_card = Table(card, colWidths=[515])
        t_card.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_light_bg),
            ('BOX', (0,0), (-1,-1), 0.75, c_accent),
            ('PADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,0), 4),
            ('BOTTOMPADDING', (0,0), (-1,0), 2),
        ]))
        story.append(t_card)
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 6))
    story.append(PageBreak()) # Page 3

    # ------------------ SECTION 5: IPR & PATENTABILITY CLAIMS ------------------
    story.append(Paragraph("5. Intellectual Property Rights (IPR) & Patentability Framework", h1_style))
    story.append(Paragraph(
        "To establish indisputable legal validity before DSIR, the innovation is framed around clear, defensible patent claims under the Indian Patents Act, 1970 (as amended):",
        body_style
    ))

    ip_claims = [
        ("Patent Title", "Context-Aware Reconfigurable Hardware Input Device and Method for Automated Dynamic Application Mapping"),
        ("International Patent Classification (IPC)", "G06F 3/02 (Input arrangements for transferring data into form capable of being handled by computer), G06F 3/038"),
        ("Core Inventive Method Claim", "A computer-implemented method and synchronized embedded microcontroller apparatus for dynamically altering physical switch-matrix and rotary-encoder mapping profiles in response to asynchronous operating system foreground window focus transitions in sub-millisecond execution windows."),
        ("Hardware Apparatus Claim", "A multi-modal input controller comprising dual-core 32-bit MCU architecture, hardware quadrature state transition decoders, transient suppression arrays, and dual-endpoint USB communication facilitating simultaneous generic HID input and dynamic serial profile synchronization.")
    ]

    t_ip_data = [[Paragraph(f"<b>{k}</b>", table_cell_bold), Paragraph(v, table_cell)] for k, v in ip_claims]
    t_ip = Table(t_ip_data, colWidths=[140, 375])
    t_ip.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), c_table_alt),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    story.append(t_ip)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 6: PRISM SUBMISSION CHECKLIST ------------------
    story.append(Paragraph("6. Innovator Action Checklist for PRISM Submission & Screening", h1_style))
    story.append(Paragraph(
        "To ensure maximum score during TOCIC evaluation and seamless grant approval under PRISM Phase-I Category-II (up to ₹20.00 Lakhs support), execute the following steps:",
        body_style
    ))

    chk_items = [
        ("Keep Focus on Novel Method & Co-Design", "In all written summaries and presentations, highlight the 'Dynamic OS Process Hooking' and 'Sub-Millisecond Hardware Scheduler' rather than just describing it as a 'keyboard' or 'macropad'."),
        ("Include Functional Prototype Video/Photos", "Enclose clear photographs of the KiCad PCB routing, 3D printed enclosure, and a short video demonstration showing zero-latency auto-switching between Blender/VS Code."),
        ("Emphasize Make in India & Price Accessibility", "State clearly that this product replaces ₹20,000+ imported proprietary devices with an indigenously manufactured ₹3,000 device, saving foreign exchange and fostering domestic hardware R&D."),
        ("Maintain Complete Budget Proportions", "Ensure Manpower is capped at ≤20% (currently 15.6%) and Travel at ≤5% (currently 3.2%), with 10% own contribution clearly documented in the application form."),
        ("Procure Domain Expert & NOC Signatures", "Obtain the signature and seal on the 'Evaluation by Domain Knowledge Experts' sheet (Page 6) and the 'No Objection Certificate' (Page 5) from your parent organization/institute.")
    ]

    chk_data = [[Paragraph(f"<b>[√] {t}</b>", table_cell_bold), Paragraph(d, table_cell)] for t, d in chk_items]
    t_chk = Table(chk_data, colWidths=[160, 355])
    t_chk.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), c_light_bg),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 5.5)
    ]))
    story.append(t_chk)
    story.append(Spacer(1, 12))

    # ------------------ SIGN-OFF BLOCK ------------------
    sign_block = [
        [
            Paragraph("<b>Prepared by:</b><br/>Pulak Nayak<br/>Hardware & Embedded Systems Innovator", ParagraphStyle('Sign1', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=c_dark)),
            Paragraph("<b>Target Scheme:</b><br/>DSIR PRISM Phase-I Category II<br/>Govt. of India", ParagraphStyle('Sign2', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=c_dark, alignment=2))
        ]
    ]
    t_sign = Table(sign_block, colWidths=[257, 258])
    t_sign.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LINEABOVE', (0,0), (-1,0), 1, c_primary)
    ]))
    story.append(KeepTogether(t_sign))

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] PDF successfully generated: {os.path.abspath(filename)}")

if __name__ == "__main__":
    out_pdf = sys.argv[1] if len(sys.argv) > 1 else "DSIR_Product_Validity_and_Novelty_Assessment.pdf"
    build_pdf(out_pdf)
