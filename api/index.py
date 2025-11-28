from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware   # ← esta línea
from pydantic import BaseModel, Field
from typing import List
import json
import os
from docx import Document
#redeploy force

app = FastAPI()

# ← AQUÍ VA EL CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # permite todo (ideal para pruebas)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Terreno(BaseModel):
    valor_terreno_propio: float
    metros_terreno_propio: float
    valor_terreno_comun: float
    metros_terreno_comun: float

class Construccion(BaseModel):
    valor_construccion_propia: float
    metros_construccion_propia: float
    valor_construccion_comun: float  # Obligatorio
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

@app.post("/api/generar-docx")
async def generar_docx(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(400, detail="Solo JSON files")

        # Lee y valida JSON
        content = await file.read()
        data = json.loads(content)
        validated_data = DatosRequest(**data)  # Valida aquí

        # Carga plantilla (ajusta path si está en templates/)
        template_path = os.path.join(os.path.dirname(__file__), 'templates', '1785-003.docx')
        if not os.path.exists(template_path):
            # Fallback: crea doc vacío si no hay plantilla
            doc = Document()
            doc.add_heading('Documento Generado', 0)
        else:
            doc = Document(template_path)

        # Renderiza placeholders (ejemplo simple; usa jinja2-docx para complejo)
        for p in doc.paragraphs:
            for key, value in validated_data.dict().items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in p.text:
                    p.text = p.text.replace(placeholder, str(value))
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Guarda en temp y devuelve
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            doc.save(tmp.name)
            with open(tmp.name, 'rb') as f:
                return StreamingResponse(f, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                         headers={"Content-Disposition": f"attachment; filename={validated_data.archivo}.docx"})

        os.unlink(tmp.name)  # Limpia temp

    except json.JSONDecodeError:
        raise HTTPException(422, detail="JSON inválido")
    except ValueError as ve:
        raise HTTPException(422, detail=str(ve))
    except Exception as e:
        raise HTTPException(500, detail=f"Error interno: {str(e)}")
