from flask import Flask, render_template, request, redirect, send_file
import os
import pandas as pd
from fpdf import FPDF
import qrcode
import boto3
import zipfile

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
CERT_FOLDER = 'certificates'
QR_FOLDER = 'qr_codes'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize AWS S3
s3 = boto3.client('s3')
BUCKET_NAME = 'devopsproje'  # ✅ Your actual S3 bucket name

# Ensure folders exist locally
for folder in [UPLOAD_FOLDER, CERT_FOLDER, QR_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

@app.route('/')
def home():
    return redirect('/upload')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            try:
                df = pd.read_excel(file_path)
            except Exception as e:
                return f"❌ Failed to read Excel file: {str(e)}"

            if 'Name' not in df.columns:
                return "❌ 'Name' column not found in the Excel sheet"

            cert_files = []

            for name in df['Name']:
                cert_id = name.lower().replace(" ", "_")

                # 🖨️ Step 1: Generate certificate PDF
                cert_filename = os.path.join(CERT_FOLDER, f"{cert_id}.pdf")
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=24)
                pdf.set_text_color(0, 102, 204)
                pdf.cell(200, 40, txt="Certificate of Participation", ln=True, align='C')
                pdf.set_font("Arial", size=18)
                pdf.cell(200, 20, txt=f"Awarded to {name}", ln=True, align='C')

                # 🔗 Step 2: Generate S3 URL and QR Code
                s3_url = f"https://devopsproje.s3.ap-south-1.amazonaws.com/{cert_id}.pdf"

                qr = qrcode.make(s3_url)
                qr_path = os.path.join(QR_FOLDER, f"{cert_id}_qr.png")
                qr.save(qr_path)

                pdf.image(qr_path, x=80, y=100, w=50)
                pdf.output(cert_filename)
                cert_files.append(cert_filename)

                # ☁️ Step 3: Upload both PDF and QR to S3
                s3.upload_file(cert_filename, BUCKET_NAME, f"{cert_id}.pdf")
                s3.upload_file(qr_path, BUCKET_NAME, f"{cert_id}_qr.png")

                # 🗃️ Optional: Store metadata in DynamoDB (commented out)
                # dynamodb = boto3.resource('dynamodb')
                # table = dynamodb.Table('YourDynamoDBTable')
                # table.put_item(Item={"cert_id": cert_id, "name": name, "url": s3_url})

            # 🗜️ Step 4: Optionally zip all PDFs
            zip_path = os.path.join(CERT_FOLDER, 'certificates.zip')
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in cert_files:
                    zipf.write(file, os.path.basename(file))

            return send_file(zip_path, as_attachment=True)

        return "⚠️ No file selected or invalid file."
    return render_template('upload.html')

if __name__ == '__main__':
    print("🚀 Flask app starting...")
    app.run(debug=True, host='0.0.0.0')
