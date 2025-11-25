from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from docxtpl import DocxTemplate
import json
import io
import os

app = FastAPI(title="Catastro → DOCX", version="1.0")

# CORS MIDDLEWARE DE RESPALDO
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# MIDDLEWARE HTTP QUE ARREGLA TODO EN VERCEL (¡IMPrescindIBLE!)
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        response = JSONResponse(content={"detail": "Preflight OK"}, status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response

    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Modelos (sin cambios)
class Terreno(BaseModel):
    valor_terreno_propio: int = Field(..., ge=0)
    metros_terreno_propio: Optional[float] = None
    valor_terreno_comun: int = Field(..., ge=0)
    metros_terreno_comun: int = Field(..., ge=0)

class Construccion(BaseModel):
    valor_construccion_propia: int = Field(..., ge=0)
    metros_construccion_propia: int = Field(..., ge=0)
    valor_construccion_comun: int = Field(..., ge=0)
    metros_construccion_comun: int = Field(..., ge=0)

class Impuesto(BaseModel):
    recargo: Optional[float] = None
    multa: Optional[float] = None
    gastos: Optional[float] = None
    subsidios: Optional[float] = None
    suma: Optional[float] = None
    ultimo_periodo_pagado: Optional[str] = None
    impuesto_predial: Optional[float] = None
    cantidad_con_letra: Optional[str] = None

class Predio(BaseModel):
    clave_catastral: str = Field(..., pattern=r"^\d{3}-\d{2}-\d{3}-\d{2}-\d{2}-[A-Z0-9]+$")
    folio: int = Field(..., gt=0)
    direccion: str
    contribuyente: str
    terreno: Terreno
    construccion: Construccion
    impuesto: Impuesto

class DocumentoCatastral(BaseModel):
    archivo: str
    predio: List[Predio]

# Endpoints básicos
@app.get("/")
@app.get("/api")
async def root():
    return {
        "message": "API FUNCIONANDO - CORS ACTIVO",
        "status": "ok",
        "test_cors": "Prueba /api/test-cors"
    }

@app.get("/api/test-cors")
async def test_cors():
    return {"message": "¡CORS OK desde Oracle APEX!"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

# ENDPOINT ORIGINAL (para files)
@app.post("/api/generar-docx")
async def generar_docx(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Solo JSON files")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        doc_data = DocumentoCatastral.model_validate(data)
    except Exception as e:
        raise HTTPException(422, f"Error validación: {e}")

    template_path = "templates/1785-003.docx"
    if not os.path.exists(template_path):
        raise HTTPException(500, "Plantilla no encontrada")

    doc = DocxTemplate(template_path)
    doc.render(doc_data.model_dump())

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)

    nombre_archivo = doc_data.archivo + ".docx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
    )

# NUEVO ENDPOINT PARA JSON DIRECTO (ideal para APEX)
# In your main.py file

@app.post("/api/generar-json")
async def generar_json(doc_data: DocumentoCatastral):
    """Endpoint para JSON directo desde Oracle APEX (sin archivos)"""
    template_path = "templates/1785-003.docx"
    if not os.path.exists(template_path):
        raise HTTPException(500, "Plantilla no encontrada")

    try:
        doc = DocxTemplate(template_path)
        
        # --- FIX STARTS HERE ---
        # Wrap the pydantic model in a dictionary with key 'documento'
        # This makes {{ documento.predio }} work in the Word template
        context = { "documento": doc_data.model_dump() }
        doc.render(context)
        # --- FIX ENDS HERE ---

        output = io.BytesIO()
        doc.save(output)
        output.seek(0)

        nombre_archivo = doc_data.archivo
        if not nombre_archivo.endswith(".docx"):
            nombre_archivo += ".docx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{nombre_archivo}"'
            }
        )
    except Exception as e:
        # This prints the actual error to your Vercel logs/response
        raise HTTPException(500, f"Error: {str(e)}")
