from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PyPDF2 import PdfMerger

def create_route_pdf(optimized_routes, unassigned_tk_stops, selected_weekday, formatted_date):
    """Creates a PDF document with route information"""
    merger = PdfMerger()
    
    # Erstelle PDF für jede Route
    for route in optimized_routes:
        if not route['stops']:
            continue
        
        route_pdf = _create_single_route_pdf(
            route, 
            selected_weekday, 
            formatted_date
        )
        merger.append(BytesIO(route_pdf.getvalue()))

    # Erstelle PDF für unzugewiesene TK-Fälle
    if unassigned_tk_stops:
        tk_pdf = _create_tk_pdf(
            unassigned_tk_stops, 
            selected_weekday, 
            formatted_date
        )
        merger.append(BytesIO(tk_pdf.getvalue()))

    # Zusammengeführtes PDF erstellen
    output = BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)
    return output

def _create_single_route_pdf(route, selected_weekday, formatted_date):
    """Erstellt eine PDF für eine einzelne Route"""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title=f"Route: {route['vehicle']}",
        author="SAPV Oberberg",
        subject=f"Route für {selected_weekday}, {formatted_date}",
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=20,
        alignment=1
    )
    
    elements = []
    elements.extend(_create_route_section(route, title_style, styles))
    
    doc.build(elements)
    output.seek(0)
    return output

def _create_tk_pdf(tk_stops, selected_weekday, formatted_date):
    """Erstellt eine PDF für unzugewiesene TK-Fälle"""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title="Unzugewiesene TK-Fälle",
        author="SAPV Oberberg",
        subject=f"TK-Fälle für {selected_weekday}, {formatted_date}",
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=20,
        alignment=1
    )
    
    elements = []
    elements.extend(_create_tk_section(tk_stops, title_style, styles))
    
    doc.build(elements)
    output.seek(0)
    return output

def _create_route_section(route, title_style, styles):
    """Creates PDF elements for a single route"""
    elements = []
    
    # Header
    elements.append(Paragraph(f"{route['vehicle']}", title_style))
    elements.append(Paragraph(
        f"Gesamtdauer: {route['duration_hrs']} / {route['max_hours']} Stunden - {route['funktion']}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 12))
    
    # Regular stops
    regular_stops = [stop for stop in route['stops'] if stop['visit_type'] != 'TK']
    if regular_stops:
        elements.extend(_create_stops_table(regular_stops, "Hausbesuche", True, title_style, styles))
    
    # TK stops
    tk_stops = [stop for stop in route['stops'] if stop['visit_type'] == 'TK']
    if tk_stops:
        elements.extend(_create_stops_table(tk_stops, "Telefonkontakte", False, title_style, styles))
    
    return elements

def _create_tk_section(tk_stops, title_style, styles):
    """Creates PDF elements for unassigned TK stops"""
    return _create_stops_table(tk_stops, "Nicht zugeordnete Telefonkontakte", False, title_style, styles)

def _create_stops_table(stops, title, include_number, title_style, styles):
    """Creates a table for stops"""
    elements = []
    elements.append(Paragraph(title, title_style))
    
    # Define headers
    headers = ['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']
    if include_number:
        headers.insert(0, 'Nr.')
    
    data = [headers]
    
    # Add stops
    for i, stop in enumerate(stops, 1):
        row = [
            stop['patient'],
            stop.get('visit_type', 'TK'),
            Paragraph(create_maps_url(stop['address']), styles['Normal']),
            stop.get('time_info', ''),
            stop.get('phone_numbers', '').replace(',', '\n')
        ]
        if include_number:
            row.insert(0, str(i))
        data.append(row)
    
    # Create and style table
    table = Table(data, repeatRows=1)
    table.setStyle(_get_table_style())
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    return elements

def _get_table_style():
    """Returns the common table style"""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]) 

def create_maps_url(address):
    """Create Google Maps URL for direct navigation"""
    base_url = "https://www.google.com/maps/dir/?api=1&destination="
    return f'<link href="{base_url}{address.replace(" ", "+")}">{address}</link>' 