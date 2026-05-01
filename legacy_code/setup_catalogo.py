import os
import json
import ezdxf
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = BASE_DIR / "libreria_dxf"
CATALOG_PATH = BASE_DIR / "catalogo.json"

def crear_letra_A_test():
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Dibujamos una 'A' sencilla con polil├¡neas, asumiendo origin 0,0
    # y una altura base de 100mm.
    # Contorno exterior de la A
    exterior = [
        (0, 0),
        (40, 100),
        (60, 100),
        (100, 0),
        (80, 0),
        (65, 40),
        (35, 40),
        (20, 0),
        (0, 0)
    ]
    # Hueco interno
    interior = [
        (40, 55),
        (50, 80),
        (60, 55),
        (40, 55)
    ]
    
    # Lo agregamos asumiendo capa default
    msp.add_lwpolyline(exterior)
    msp.add_lwpolyline(interior)
    
    ruta = LIBRARY_DIR / "letra_A.dxf"
    doc.saveas(str(ruta))
    print(f"Letra A base creada en {ruta}")

def iniciar_libreria():
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        
    crear_letra_A_test()
    
    catalogo = {
        "piezas": [
            {
                "id": "letra_a",
                "nombre": "Letra A",
                "ruta": "libreria_dxf/letra_A.dxf",
                "descripcion": "Letra may├║scula A est├índar base 100mm"
            }
        ]
    }
    
    with CATALOG_PATH.open("w", encoding='utf-8') as f:
        json.dump(catalogo, f, indent=4)
    print("Cat├ílogo inicializado con ├®xito.")

if __name__ == "__main__":
    iniciar_libreria()
