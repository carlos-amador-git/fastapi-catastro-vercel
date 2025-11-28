from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import json
import os
import tempfile

app = FastAPI()

# ====== CORS CONFIGURATION ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: ["https://gf7ef8efb74e614-h00tgkrff41zo9rl.adb.us-phoenix-1.oraclecloudapps.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== MODELS ======
class Terreno(BaseModel):
    valor_terreno_propio: float
    metros_terreno_propio: float
    valor_terreno_comun: float
    metros_terreno_comun: float

class Construccion(BaseModel):
    valor_construccion_propia: float
    metros_construccion_propia: float
    valor_construccion_comun: float
    metros_construccion_comun: float

class Impuesto(BaseModel):
    impuesto_predial: float
    cantidad_con_letra: str

class Predio(BaseModel):
    clave_catastral: str = Field(..., pattern=r'^\d{3}-\d{2}-\d{3}-\d{2}-\d{2}-[A-Z0-9]+$')
    folio: int
    direccion: str
    contribuyente: str
    terreno: Terreno
    construccion: Construccion
    impuesto: Impuesto

class DatosRequest(BaseModel):
    archivo: str
    predio: List[Predio]

# ====== ENDPOINTS ======
@app.get("/")
async def root():
    return {"status": "API running", "message": "Use POST /api/generar-docx"}

@app.post("/api/generar-docx")
async def generar_docx(file: UploadFile = File(...)):
    try:
        # Validar tipo de archivo
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos JSON")
        
        # Leer y parsear JSON
        content = await file.read()
        data = json.loads(content)
        
        # Validar estructura con Pydantic
        validated_data = DatosRequest(**data)
        
        # Buscar plantilla
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', '1785-003.docx')
        
        if os.path.exists(template_path):
            doc = Document(template_path)
        else:
            # Crear documento vacío si no hay plantilla
            doc = Document()
            doc.add_heading('Documento Generado', 0)
            doc.add_paragraph(f"Archivo: {validated_data.archivo}")
        
        # Reemplazar placeholders (ejemplo básico)
        data_dict = validated_data.dict()
        for paragraph in doc.paragraphs:
            original_text = paragraph.text
            for key, value in data_dict.items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in original_text:
                    original_text = original_text.replace(placeholder, str(value))
            
            if original_text != paragraph.text:
                paragraph.text = original_text
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        
        # Guardar en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            doc.save(tmp.name)
            tmp_path = tmp.name
        
        # Leer archivo y devolverlo
        def file_iterator():
            with open(tmp_path, 'rb') as f:
                yield from f
            os.unlink(tmp_path)  # Limpiar después de enviar
        
        return StreamingResponse(
            file_iterator(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={validated_data.archivo}.docx",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="JSON inválido")
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=f"Error de validación: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Para Vercel - No usar handler directo
