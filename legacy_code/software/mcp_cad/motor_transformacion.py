import ezdxf
from ezdxf import bbox
from ezdxf.math import Matrix44, BoundingBox
import sys

def transformar_dxf(origen, destino, alt_objetivo, rotacion_grados):
    """
    Toma un DXF, calcula su caja delimitadora, lo escala para que 
    su Alto (Y) coincida con alt_objetivo, y lo rota si es necesario.
    """
    print(f"Cargando archivo base: {origen}")
    doc = ezdxf.readfile(origen)
    msp = doc.modelspace()

    # 1. Calcular el bounding box real de todas las entidades soportadas
    scene_bbox = bbox.extents(msp)
    if not scene_bbox.has_data:
        print("El archivo parece vac├¡o o no tiene polil├¡neas legibles.")
        return False

    altura_original = scene_bbox.extmax.y - scene_bbox.extmin.y
    print(f"Altura original detectada: {altura_original:.2f} mm")
    
    if altura_original <= 0.01:
        print("Altura nula, cancelando.")
        return False
        
    # 2. Calcular Escala y armar Matrices
    zoom = 1.0
    if alt_objetivo is not None:
        zoom = alt_objetivo / altura_original

    # Mover al origen (0,0) para escalar y rotar desde su centroide o base
    centro_base_x = scene_bbox.extmin.x + (scene_bbox.extmax.x - scene_bbox.extmin.x)/2
    centro_base_y = scene_bbox.extmin.y + (scene_bbox.extmax.y - scene_bbox.extmin.y)/2
    
    transformacion = (
        Matrix44.translate(-centro_base_x, -centro_base_y, 0) # al origen
        @ Matrix44.scale(zoom, zoom, 1.0) # escalar
        @ Matrix44.z_rotate(rotacion_grados * 3.14159 / 180.0) # rotar
    )
    
    # 3. Aplicar transformacion a todo y pasarlo a la capa PERFIL de nuestro sistema
    for entity in msp:
        entity.transform(transformacion)
        entity.dxf.layer = 'PERFIL' # Para que generador_cam sepa que lo tiene que cortar
        entity.dxf.color = 1 # Rojo
        
    doc.saveas(destino)
    print(f"Transformaci├│n lista: Escala {zoom:.2f}x | Rotaci├│n {rotacion_grados}┬░")
    print(f"Guardado como: {destino}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso: python motor_transformacion.py <origen_dxf> <destino_dxf> <altura_mm> <grados>")
    else:
        transformar_dxf(sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
