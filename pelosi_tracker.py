import json
import os
import smtplib
from email.message import EmailMessage
import requests

API_URL = "https://api.quiverquant.com/beta/historical/congresstrading/Nancy%20Pelosi-P000197"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO")

def send_email_alert(message_content):
    if not EMAIL_USER or not EMAIL_PASSWORD or not EMAIL_TO:
        print("Credenciales de correo no configuradas.")
        return

    msg = EmailMessage()
    msg.set_content(message_content)
    msg["Subject"] = "🚨 ¡Alerta: Movimiento en el portafolio de Nancy Pelosi!"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Correo de alerta enviado exitosamente.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

def get_current_trades():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al conectar con la API: {response.status_code}")
            return None
    except Exception as e:
        print(f"Excepción en la petición: {e}")
        return None

def main():
    print("Revisando portafolio de Nancy Pelosi...")
    current_data = get_current_trades()
    
    if not current_data:
        print("No se pudo obtener la información en esta ejecución.")
        return

    filename = "last_portfolio.json"
    
    # Si el archivo no existe (primera ejecución), lo creamos sin disparar alerta
    if not os.path.exists(filename):
        print("Archivo inicial no encontrado. Creando línea base...")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=4, ensure_ascii=False)
        return

    # Cargar el registro anterior
    with open(filename, "r", encoding="utf-8") as f:
        try:
            previous_data = json.load(f)
        except json.JSONDecodeError:
            previous_data = []

    # Comparar datos
    if current_data != previous_data:
        print("¡Cambio detectado en el portafolio!")
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=4, ensure_ascii=False)
            
        cuerpo_mensaje = (
            "Se ha detectado un nuevo cambio o transacción en el portafolio de Nancy Pelosi.\n\n"
            "Puedes revisar los detalles directamente en la plataforma:\n"
            "https://www.quiverquant.com/congresstrading/politician/Nancy%20Pelosi-P000197"
        )
        send_email_alert(cuerpo_mensaje)
    else:
        print("No hay cambios nuevos en el portafolio.")

if __name__ == "__main__":
    main()
