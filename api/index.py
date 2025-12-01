from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os
import io # Importante para manejar archivos en memoria
from docxtpl import DocxTemplate # Importación correcta para plantillas

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (TUS MODELOS Pydantic SE QUEDAN IGUAL) ...
# Pégalos aquí (Terreno, Construccion, etc.)
# ...

class Terreno(BaseModel):
    valor_terreno_propio: Optional[str] = None
    metros_terreno_propio: Optional[str] = None
    valor_terreno_comun: Optional[str] = None
    metros_terreno_comun: Optional[str] = None

class Construccion(BaseModel):
    valor_construccion_propia: Optional[str] = None
    metros_construccion_propia: Optional[str] = None
    valor_construccion_comun: Optional[str] = None
    metros_construccion_comun: Optional[str] = None

class Impuesto(BaseModel):
    recargo: Optional[str] = None
    multa: Optional[str] = None
    gastos: Optional[str] = None
    subsidios: Optional[str] = None
    suma: Optional[str] = None
    ultimo_periodo_pagado: Optional[str] = None
    impuesto_predial: Optional[str] = None
    monto_a_pagar: Optional[str] = None
    cantidad_con_letra: Optional[str] = None

class Documento(BaseModel):
    fecha_actual: Optional[str] = None
    tipo_documento: int = Field
    fecha_documento: Optional[str] = None
    fecha_ini_vigencia: Optional[str] = None
    fecha_fin_vigencia: Optional[str] = None


class Predio(BaseModel):
    clave_catastral: Optional[str] = None
    folio: int = Field
    direccion: Optional[str] = None
    contribuyente: Optional[str] = None
    terreno: Terreno
    construccion: Construccion
    impuesto: Impuesto
    documento: Documento

class DocumentoCatastral(BaseModel):
    archivo: Optional[str] = None
    plantilla_tipo_documento: Optional[str] = None
    predio: List[Predio]

# ===== ENDPOINTS =====
@app.get("/api")
def api_root():
    return {"status": "ok", "endpoints": ["/api/generar-docx"]}

@app.post("/api/generar-docx")
async def generar_docx(file: UploadFile = File(...)):    
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Solo archivos .json")

    try:
        content = await file.read()
        data = json.loads(content)
        doc_data = DocumentoCatastral.model_validate(data)
    except Exception as e:
        print(f"Error validacion: {e}") # Log para ver en Vercel dashboard
        raise HTTPException(422, f"Error en validación: {str(e)}")

    # Validar ruta de plantilla
    # En Vercel, los archivos estáticos a veces requieren manejo de rutas absoluto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "templates", doc_data.plantilla_tipo_documento)
    
    # Fallback por si la estructura de carpetas varía en el deploy
    if not os.path.exists(template_path):
        # Intenta buscar en la raíz si no está en templates/
        template_path = doc_data.plantilla_tipo_documento 
        
    if not os.path.exists(template_path):
        raise HTTPException(500, f"Plantilla no encontrada en: {template_path}")

    try:
        doc = DocxTemplate(template_path)

        # Renderizar
        contexto = doc_data.model_dump()
        doc.render(contexto)

        # GUARDAR EN MEMORIA (RAM) - Evita el error de "Read-only file system"
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0) # Regresar el puntero al inicio del archivo

        # Nombre del archivo de salida
        nombre_salida = doc_data.archivo.replace(".docx", "_generado.docx") if doc_data.archivo else "documento_generado.docx"

        # Retornar como StreamingResponse
        # Esto envía el archivo binario directamente al navegador
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={nombre_salida}",
                "Access-Control-Expose-Headers": "Content-Disposition" # Ayuda al frontend a leer el nombre
            }
        )

    except Exception as e:
        print(f"Error generando docx: {e}")
        raise HTTPException(500, f"Error generando documento: {str(e)}")
