import io
import json
import os
import smtplib
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from email.message import EmailMessage

import requests

APELLIDO = "Pelosi"
FILENAME = "last_portfolio.json"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def send_email_alert(subject, body):
    if not EMAIL_USER or not EMAIL_PASSWORD or not EMAIL_TO:
        print("Credenciales de correo no configuradas.")
        return
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Correo enviado exitosamente.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")


def alert_failure(motivo):
    """Avisa por correo que el rastreador falló y marca el job en rojo."""
    print(f"FALLO: {motivo}")
    send_email_alert(
        "⚠️ El rastreador de Pelosi NO está funcionando",
        "El script se ejecutó pero no pudo leer los datos oficiales.\n\n"
        f"Motivo: {motivo}\n\n"
        "Revisa el log en la pestaña Actions de tu repositorio.",
    )
    sys.exit(1)


def get_filings(year):
    """Descarga el índice oficial del House Clerk.
    Devuelve (reportes_de_pelosi, total_de_registros_del_índice)."""
    url = f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP"
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml_name = next(n for n in z.namelist() if n.lower().endswith(".xml"))
        root = ET.fromstring(z.read(xml_name))

    total = sum(1 for _ in root.iter("Member"))

    filings = []
    for m in root.iter("Member"):
        last = (m.findtext("Last") or "").strip()
        tipo = (m.findtext("FilingType") or "").strip()
        if last.lower() == APELLIDO.lower() and tipo == "P":  # P = reporte de operaciones
            doc_id = (m.findtext("DocID") or "").strip()
            filings.append({
                "doc_id": doc_id,
                "fecha": (m.findtext("FilingDate") or "").strip(),
                "year": year,
                "pdf": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf",
            })
    return filings, total


def load_previous():
    if not os.path.exists(FILENAME):
        return None
    with open(FILENAME, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save(data):
    with open(FILENAME, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def main():
    print("Revisando reportes oficiales de Nancy Pelosi...")
    year = datetime.now().year

    # En enero también revisamos el año anterior por si quedó algo pendiente
    years = [year]
    if datetime.now().month == 1:
        years.append(year - 1)

    current = []
    lecturas_ok = 0
    errores = []
    total_indice = 0

    for y in years:
        try:
            filings, total = get_filings(y)
            if total == 0:
                errores.append(f"El índice de {y} llegó vacío (0 registros).")
                continue
            current += filings
            total_indice += total
            lecturas_ok += 1
            print(f"{y}: {total} registros en el índice, {len(filings)} de Pelosi.")
        except Exception as e:
            errores.append(f"Error leyendo el índice de {y}: {e}")

    # Si no se pudo leer NINGÚN año, avisamos y fallamos
    if lecturas_ok == 0:
        alert_failure(" | ".join(errores))

    previous = load_previous()

    # Primera ejecución: se crea la línea base sin avisar
    if previous is None:
        print("Archivo inicial no encontrado. Creando línea base...")
        save(current)
        return

    # Validación: si antes había reportes y ahora hay menos, el formato pudo cambiar
    previous_same_years = [p for p in previous if p.get("year") in years]
    if previous_same_years and len(current) < len(previous_same_years):
        alert_failure(
            f"Antes había {len(previous_same_years)} reportes de Pelosi y ahora solo "
            f"{len(current)}. Es posible que el formato del archivo oficial haya cambiado."
        )

    # Aviso mensual de que el rastreador sigue vivo (día 1 de cada mes)
    if datetime.now().day == 1:
        send_email_alert(
            "✅ El rastreador de Pelosi sigue funcionando",
            "Lectura correcta del archivo oficial.\n"
            f"Registros en el índice: {total_indice}.\n"
            f"Reportes de Pelosi registrados: {len(current)}.\n"
            "No es necesario hacer nada.",
        )

    seen_ids = {p["doc_id"] for p in previous}
    nuevos = [c for c in current if c["doc_id"] not in seen_ids]

    if nuevos:
        print(f"¡{len(nuevos)} reporte(s) nuevo(s) detectado(s)!")
        # Conservamos lo de años anteriores que no se leyó hoy
        merged = [p for p in previous if p.get("year") not in years] + current
        save(merged)

        lineas = [f"- Presentado el {n['fecha']}: {n['pdf']}" for n in nuevos]
        cuerpo = (
            "Nancy Pelosi presentó un nuevo reporte de operaciones bursátiles:\n\n"
            + "\n".join(lineas)
            + "\n\nAbre el PDF para ver el detalle de las operaciones."
        )
        send_email_alert("🚨 Nuevo reporte de operaciones de Nancy Pelosi", cuerpo)
    else:
        print("No hay reportes nuevos.")


if __name__ == "__main__":
    main()
