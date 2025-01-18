from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from PyPDF2 import PdfMerger

def create_route_pdf(optimized_routes, unassigned_tk_stops, unassigned_regular_stops, selected_weekday, formatted_date):
    # Erstellt ein PDF-Dokument mit Route-Informationen
    merger = PdfMerger()
    
    # Erstelle PDF für jeden Mitarbeiter
    for route in optimized_routes:
        if not route['stops']:
            continue
        
        route_pdf = _create_single_route_pdf(
            route, 
            selected_weekday, 
            formatted_date
        )
        merger.append(BytesIO(route_pdf.getvalue()))

    # Erstelle PDF für unzugewiesene Hausbesuche
    if unassigned_regular_stops:
        regular_pdf = _create_unassigned_regular_pdf(
            unassigned_regular_stops,
            selected_weekday,
            formatted_date
        )
        merger.append(BytesIO(regular_pdf.getvalue()))

    # Erstelle PDF für unzugewiesene Telefonkontakte
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
    # Erstellt eine PDF für eine einzelne Route
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title=f"Optimierte Route: {route['vehicle']}",
        author="PalliRoute",
        subject=f"Optimierte Route für {selected_weekday}, {formatted_date}",
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
    # Erstellt eine PDF für unzugewiesene Telefonkontakte
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title="Unzugewiesene Telefonkontakte",
        author="PalliRoute",
        subject=f"Unzugewiesene Telefonkontakte für {selected_weekday}, {formatted_date}",
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

def _create_unassigned_regular_pdf(regular_stops, selected_weekday, formatted_date):
    # Erstellt eine PDF für unzugewiesene Hausbesuche
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm,
        title="Unzugewiesene Hausbesuche",
        author="PalliRoute",
        subject=f"Unzugewiesene Hausbesuche für {selected_weekday}, {formatted_date}",
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
    elements.extend(_create_regular_section(regular_stops, title_style, styles))
    
    doc.build(elements)
    output.seek(0)
    return output

def _create_route_section(route, title_style, styles):
    # Erstellt PDF-Elemente für eine einzelne Route
    elements = []
    
    # Header
    elements.append(Paragraph(f"{route['vehicle']}", title_style))
    elements.append(Paragraph(
        f"Gesamtdauer: {route['duration_hrs']} / {route['max_hours']} Stunden - {route['funktion']}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 12))
    
    # Hausbesuche
    regular_stops = [stop for stop in route['stops'] if stop['visit_type'] != 'TK']
    if regular_stops:
        elements.extend(_create_stops_table(regular_stops, "Hausbesuche", True, title_style, styles))
    
    # Telefonkontakte
    tk_stops = [stop for stop in route['stops'] if stop['visit_type'] == 'TK']
    if tk_stops:
        elements.extend(_create_stops_table(tk_stops, "Telefonkontakte", False, title_style, styles))
    
    return elements

def _create_tk_section(tk_stops, title_style, styles):
    # Erstellt PDF-Elemente für unzugewiesene Telefonkontakte
    return _create_stops_table(tk_stops, "Unzugewiesene Telefonkontakte", False, title_style, styles)

def _create_regular_section(regular_stops, title_style, styles):
    # Erstellt PDF-Elemente für unzugewiesene Hausbesuche
    elements = []
    elements.append(Paragraph("Unzugewiesene Hausbesuche", title_style))
    
    # Header
    headers = ['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']
    data = [headers]
    
    for stop in regular_stops:
        data.append([
            stop['patient'],
            stop['visit_type'],
            Paragraph(create_maps_url(stop['address']), styles['Normal']),
            stop.get('time_info', ''),
            stop.get('phone_numbers', '').replace(',', '\n')
        ])
    
    table = Table(data, repeatRows=1)
    table.setStyle(_get_table_style())
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    return elements 

def _create_stops_table(stops, title, include_number, title_style, styles):
    # Erstellt eine Tabelle für Besuche
    elements = []
    elements.append(Paragraph(title, title_style))
    
    # Header
    headers = ['Patient', 'Besuchsart', 'Adresse', 'Uhrzeit/Info', 'Telefon']
    if include_number:
        headers.insert(0, 'Nr.')
    
    data = [headers]
    
    # Besuche
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
    
    # Tabelle erstellen und stylen
    table = Table(data, repeatRows=1)
    table.setStyle(_get_table_style())
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    return elements

def _get_table_style():
    # Gibt die gemeinsame Tabellen-Stil zurück
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
    # Erstellt eine Google Maps-URL für direkte Navigation
    base_url = "https://www.google.com/maps/dir/?api=1&destination="
    return f'<link href="{base_url}{address.replace(" ", "+")}">{address}</link>' 


