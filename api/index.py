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

# CORS - Permite llamadas desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: específica tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== MODELOS =====
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

# ===== ENDPOINTS =====
@app.get("/")
def root():
    return {"status": "ok", "message": "API funcionando correctamente"}

@app.get("/api")
def api_root():
    return {"status": "ok", "endpoints": ["/api/generar-docx"]}

@app.post("/api/generar-docx")
async def generar_docx(file: UploadFile = File(...)):
    """
    Recibe un archivo JSON y genera un documento DOCX
    """
    try:
        # Validar que sea JSON
        if not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400, 
                detail="Solo se permiten archivos JSON"
            )
        
        # Leer y validar contenido
        content = await file.read()
        data = json.loads(content)
        validated_data = DatosRequest(**data)
        
        # Crear documento Word
        doc = Document()
        doc.add_heading('Documento Generado Automáticamente', 0)
        doc.add_paragraph(f"Archivo: {validated_data.archivo}")
        doc.add_paragraph(f"Total de predios: {len(validated_data.predio)}")
        doc.add_paragraph("")  # Espacio
        
        # Agregar información de cada predio
        for idx, predio in enumerate(validated_data.predio, 1):
            doc.add_heading(f'Predio #{idx}', level=1)
            
            # Información básica
            doc.add_paragraph(f"📋 Clave Catastral: {predio.clave_catastral}")
            doc.add_paragraph(f"📄 Folio: {predio.folio}")
            doc.add_paragraph(f"📍 Dirección: {predio.direccion}")
            doc.add_paragraph(f"👤 Contribuyente: {predio.contribuyente}")
            
            # Terreno
            doc.add_heading('Terreno', level=2)
            doc.add_paragraph(f"• Valor propio: ${predio.terreno.valor_terreno_propio:,.2f}")
            doc.add_paragraph(f"• Metros propio: {predio.terreno.metros_terreno_propio} m²")
            doc.add_paragraph(f"• Valor común: ${predio.terreno.valor_terreno_comun:,.2f}")
            doc.add_paragraph(f"• Metros común: {predio.terreno.metros_terreno_comun} m²")
            
            # Construcción
            doc.add_heading('Construcción', level=2)
            doc.add_paragraph(f"• Valor propia: ${predio.construccion.valor_construccion_propia:,.2f}")
            doc.add_paragraph(f"• Metros propia: {predio.construccion.metros_construccion_propia} m²")
            doc.add_paragraph(f"• Valor común: ${predio.construccion.valor_construccion_comun:,.2f}")
            doc.add_paragraph(f"• Metros común: {predio.construccion.metros_construccion_comun} m²")
            
            # Impuesto
            doc.add_heading('Impuesto Predial', level=2)
            doc.add_paragraph(f"💰 Monto: ${predio.impuesto.impuesto_predial:,.2f}")
            doc.add_paragraph(f"📝 En letra: {predio.impuesto.cantidad_con_letra}")
            
            doc.add_paragraph("")  # Espacio entre predios
        
        # Guardar en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            doc.save(tmp.name)
            tmp_path = tmp.name
        
        # Crear generador para enviar archivo
        def file_iterator():
            with open(tmp_path, 'rb') as f:
                yield from f
            # Eliminar archivo temporal después de enviar
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        # Retornar archivo
        return StreamingResponse(
            file_iterator(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={validated_data.archivo}.docx",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=422, 
            detail=f"JSON inválido: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422, 
            detail=f"Error de validación: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno del servidor: {str(e)}"
        )

# Vercel necesita que exportes 'app'
# No agregues 'handler' ni nada más al final
